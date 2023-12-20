import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import boto3
import structlog
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from fastapi.exceptions import HTTPException

from rubintv.config import config


class S3Client:
    def __init__(self, profile_name: str) -> None:
        endpoint_url = config.s3_endpoint_url
        session = boto3.Session(
            region_name="us-east-1", profile_name=profile_name
        )
        if endpoint_url is not None and not endpoint_url == "testing":
            self._client = session.client("s3", endpoint_url=endpoint_url)
        else:
            self._client = session.client("s3")
        self._bucket_name = profile_name

    def list_objects(self, prefix: str) -> list[dict[str, str]]:
        objects = []
        response = self._client.list_objects_v2(
            Bucket=self._bucket_name, Prefix=prefix
        )
        while True:
            for content in response.get("Contents", []):
                object = {}
                object["key"] = content["Key"]
                object["hash"] = content["ETag"].strip('"')
                objects.append(object)
            if "NextContinuationToken" not in response:
                break
            response = self._client.list_objects_v2(
                Bucket=self._bucket_name,
                Prefix=prefix,
                ContinuationToken=response["NextContinuationToken"],
            )
        return objects

    def _get_object(self, key: str) -> dict | None:
        logger = structlog.get_logger(__name__)
        try:
            obj = self._client.get_object(Bucket=self._bucket_name, Key=key)
            return json.loads(obj["Body"].read())
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.info(f"Object for key: {key} not found.")
            return None

    async def async_get_object(self, key: str) -> dict | None:
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=3)
        return await loop.run_in_executor(executor, self._get_object, key)

    def get_raw_object(self, key: str) -> StreamingBody:
        try:
            data = self._client.get_object(Bucket=self._bucket_name, Key=key)
            return data["Body"]
        except ClientError:
            raise HTTPException(
                status_code=404, detail=f"No such file for: {key}"
            )

    async def get_presigned_url(self, key: str) -> str:
        logger = structlog.get_logger(__name__)
        try:
            url = self._client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self._bucket_name, "Key": key},
                ExpiresIn=300,
            )
        except ClientError:
            logger.error(f"Couldn't generate URL for key: {key}")
            return ""
        return url
