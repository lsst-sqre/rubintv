import json
import logging
import random
from datetime import date
from itertools import chain
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from lsst.ts.rubintv.models.models import (
    Channel,
    Event,
    NightReportData,
    get_current_day_obs,
)
from lsst.ts.rubintv.models.models_helpers import find_first
from lsst.ts.rubintv.models.models_init import Camera, Location


class RubinDataMocker:
    FIRST_SEQ = 0

    def __init__(
        self,
        locations: list[Location],
        day_obs: date = get_current_day_obs(),
        s3_required: bool = False,
    ) -> None:
        """
        Initialize the RubinDataMocker instance.

        Parameters
        ----------
        locations : list[Location]
            A list of Location objects representing various observation
            locations.
        day_obs : date, optional
            The observation day, defaults to today.
        s3_required : bool, optional
            Boolean flag to indicate if S3 operations are required, defaults
            to False.
        """
        self.last_seq: dict[str, int] = {}
        self._locations = locations
        if s3_required:
            self.s3_client = boto3.client("s3")
            self.create_buckets()
        self.s3_required = s3_required
        self.day_obs = day_obs
        self.location_channels: dict[str, list[Channel]] = {}
        self.seq_objs: dict[str, list[dict[str, str]]] = {}
        self.empty_channel: dict[str, str] = {}
        self.events: dict[str, list[Event]] = {}
        self.metadata: dict[str, dict[str, str]] = {}

        metadata = {f"col{n}": "dummy" for n in range(1, 6)}
        self.md_json = json.dumps(metadata)

        self.nr_text = r"""
        This is line one.
        This is line two.
        This    spacing is intentional.
        """

        self.nr_qa_plots = {
            "Link to RubinTV githib": "https://github.com/lsst-ts/rubintv",
            "Link to LSST": "https://www.lsst.org",
        }

        self.nr_groups = ["coverage", "elana", "test"]
        self.nr_metadata: dict[str, dict[str, str]] = {}
        self.nr_plots: dict[str, list[NightReportData]] = {}

        self.mock_up_data()

    def delete_buckets(self) -> None:
        if self.s3_required:
            s3 = boto3.resource("s3", region_name="us-east-1")
            for location in self._locations:
                bucket_name = location.bucket_name
                bucket = s3.Bucket(bucket_name)
                print(f"Emptying bucket: {bucket_name}")
                bucket.objects.all().delete()

    def create_buckets(self) -> None:
        for location in self._locations:
            bucket_name = location.bucket_name
            # mock bucket requires a legit region name
            s3 = boto3.resource("s3", region_name="us-east-1")
            print(f"Creating bucket: {bucket_name}")
            bucket = s3.Bucket(bucket_name)
            bucket.create()

    def mock_up_data(self) -> None:
        """
        Populate mock data for cameras and channels based on the current day's
        observation.

        Returns
        -------
        None
        """

        # TODO: keep adding to the add_data() functions
        # see DM-44838 https://rubinobs.atlassian.net/browse/DM-44838

        for location in self._locations:
            loc_name = location.name
            self.events[loc_name] = []
            self.location_channels[loc_name] = []
            groups = location.camera_groups.values()
            camera_names = list(chain(*groups))
            cameras = location.cameras
            for cam_name in camera_names:
                camera: Camera | None
                if camera := find_first(cameras, "name", cam_name):
                    if not camera.online:
                        continue
                    loc_cam = f"{loc_name}/{cam_name}"

                    self.location_channels[loc_name].append(camera.channels)

                    self.add_seq_objs(location, camera)

                    metadata = self.add_camera_metadata(location, camera)
                    self.metadata[loc_cam] = metadata

    def add_seq_objs(self, location: Location, camera: Camera) -> None:
        """
        Generate mock channel objects and an empty channel string for a given
        camera and location.

        Parameters
        ----------
        location : Location
            The location object representing the observation location.
        camera : Camera
            The camera object for which the channel objects are being mocked.
        empty_channel : str
            The name of the channel to leave empty.

        Returns
        -------
        tuple[list[dict[str, str]], str]
            A tuple containing a list of mock channel dictionaries and an
            updated empty channel string.
        """

        channel_data: list[dict[str, str]] = []
        loc_cam = f"{location.name}/{camera.name}"
        iterations = 8

        empty_channel = ""
        seq_chans = [chan.name for chan in camera.seq_channels()]
        if seq_chans:
            empty_channel = random.choice(seq_chans)

        for channel in camera.channels:
            loc_cam_chan = f"{loc_cam}/{channel.name}"
            start = self.last_seq.get(loc_cam_chan, self.FIRST_SEQ)

            if empty_channel == channel.name:
                self.empty_channel[loc_cam] = empty_channel
                continue

            for index in range(start, start + iterations):
                seq_num = f"{index:06}"

                # randomly add "final" sequence for per-day channels
                if channel.per_day and index == start + iterations - 1:
                    seq_num = random.choice((seq_num, "final"))

                event_obj = self.generate_event(
                    location.bucket_name, camera.name, channel.name, seq_num
                )

                channel_data.append(event_obj)
                self.last_seq[loc_cam_chan] = index
                if seq_num == "final":
                    print(f"final written for {loc_cam_chan}")
                    continue

        # store the objects for testing against
        if loc_cam in self.seq_objs:
            self.seq_objs[loc_cam].extend(channel_data)
            self.events[loc_cam].extend(self.dicts_to_events(channel_data))
        else:
            self.seq_objs[loc_cam] = channel_data
            self.events[loc_cam] = self.dicts_to_events(channel_data)

    def add_camera_metadata(self, location: Location, camera: Camera) -> dict[str, str]:
        """
        Mock metadata for a given camera at a specified location.

        Parameters
        ----------
        location : Location
            The location for which the metadata is being mocked.
        camera : Camera
            The camera for which the metadata is being mocked.

        Returns
        -------
        dict[str, str]
            A dictionary containing mocked metadata.
        """

        key = f"{camera.name}/{self.day_obs}/metadata.json"
        if self.s3_required:
            self.upload_fileobj(self.md_json, location.bucket_name, key)
        metadata = {key: self.md_json}
        return metadata

    def mock_night_report_metadata(self, location: Location, camera: Camera) -> None:
        key = f"{camera.name}/{self.day_obs}/night_report/md.json"
        bucket_name = location.bucket_name
        text_dict = {}
        for idx in range(1, 4):
            text_dict[f"text_{idx}"] = self.nr_text
        if self.s3_required:
            text_json = json.dumps(text_dict)
            self.upload_fileobj(text_json, bucket_name, key)
        self.nr_metadata[f"{location.name}/{camera.name}"] = text_dict

    def mock_night_report_plots(self, location: Location, camera: Camera) -> None:
        bucket_name = location.bucket_name
        loc_cam = f"{location.name}/{camera.name}"
        self.nr_plots[loc_cam] = []
        for group in self.nr_groups:
            for idx in range(1, 2):
                key = f"{camera.name}/{self.day_obs}/night_report/{group}/{group}_test-img0{idx}.jpg"
                hash = self.upload_image(bucket_name, key, "assets/testcard_f.jpg")
                self.nr_plots[loc_cam].append(NightReportData(key=key, hash=hash))

    def upload_image(self, bucket_name: str, key: str, img_rel_path: str) -> str:
        hash: str | None = None
        if self.s3_required:
            if self.upload_file(
                Path(__file__).parent / img_rel_path,
                bucket_name,
                key,
            ):
                hash = self.get_obj_hash(bucket_name, key)
        if hash is None:
            hash = str(random.getrandbits(128))
        return hash

    def generate_event(
        self, bucket_name: str, camera_name: str, channel_name: str, seq_num: str
    ) -> dict[str, str]:
        day_obs = self.day_obs
        key = f"{camera_name}/{day_obs}/{channel_name}/{seq_num}/mocked_event.jpg"
        hash = self.upload_image(bucket_name, key, "assets/testcard_f.jpg")
        return {"key": key, "hash": hash}

    def dicts_to_events(self, channel_dicts: list[dict[str, str]]) -> list[Event]:
        """
        Convert a list of dictionaries to a list of Event objects.

        Parameters
        ----------
        channel_dicts : list[dict[str, str]]
            List of dictionaries representing channel data.

        Returns
        -------
        list[Event]
            A list of Event objects created from the channel dictionaries.
        """
        events = [Event(**cd) for cd in channel_dicts]
        return events

    async def get_mocked_seq_events(self, location: Location) -> list[Event]:
        """
        Asynchronously retrieve sequence events for a given location.

        Parameters
        ----------
        location : Location
            The location for which to retrieve the sequence events.

        Returns
        -------
        list[Event]
            A list of Event objects representing sequence events.
        """
        events = self.events.get(location.name)
        if events is None:
            return []
        channels = self.location_channels[location.name]
        seq_chan_names = [c for c in channels if not c.per_day]
        seq_chan_events = [e for e in events if e.channel_name in seq_chan_names]
        return seq_chan_events

    def upload_file(self, file_name: Path | str, bucket_name: str, key: str) -> bool:
        """Upload a file to an S3 bucket.

        Parameters
        ----------
        file_name: `Path` | `str`
            Name/path of file to upload.
        bucket: `str`
            Name of bucket to upload to.
        key: `str`
            Name for the file in the bucket.

        Returns
        -------
        uploaded: `bool`
            True if file was uploaded, else False.
        """
        try:
            self.s3_client.upload_file(file_name, bucket_name, key)
        except ClientError as e:
            logging.error(e)
            return False
        return True

    def upload_fileobj(self, json_str: str, bucket_name: str, key: str) -> bool:
        """Upload a file-like object to an S3 bucket.

        Parameters
        ----------
        file_obj:
            File-like object to upload.
        bucket: `str`
            Name of bucket to upload to.
        key: `str`
            Name for the file in the bucket.

        Returns
        -------
        uploaded: `bool`
            True if object was uploaded, else False.
        """
        try:
            self.s3_client.put_object(Bucket=bucket_name, Body=json_str, Key=key)
        except ClientError as e:
            logging.error(e)
            return False
        return True

    def get_obj_hash(self, bucket_name: str, key: str) -> str:
        """
        Retrieve the hash (ETag) of an object stored in an S3 bucket.

        Parameters
        ----------
        bucket_name : str
            Name of the S3 bucket.
        key : str
            S3 key of the object.

        Returns
        -------
        str
            The hash (ETag) of the object if retrievable, empty string
            otherwise.
        """
        try:
            res = self.s3_client.get_object_attributes(
                Bucket=bucket_name, Key=key, ObjectAttributes=["ETag"]
            )
        except ClientError as e:
            logging.error(e)
            return ""
        return res["ETag"]
