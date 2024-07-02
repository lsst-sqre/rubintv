from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from lsst.ts.rubintv.config import rubintv_logger
from lsst.ts.rubintv.s3client import S3Client

proxies_router = APIRouter()
logger = rubintv_logger()


@proxies_router.get(
    "/event_image/{location_name}/{camera_name}/{channel_name}/{filename}",
    response_class=StreamingResponse,
    name="event_image",
)
def proxy_image(
    location_name: str,
    camera_name: str,
    channel_name: str,
    filename: str,
    request: Request,
) -> StreamingResponse:
    try:
        to_remove = "_".join((camera_name, channel_name)) + "_"
        rest = filename.replace(to_remove, "")
        date_str, seq_ext = rest.split("_")
        seq_str, ext = seq_ext.split(".")
    except ValueError:
        raise HTTPException(404, "Filename not valid.")
    key = f"{camera_name}/{date_str}/{channel_name}/{seq_str}/{filename}"

    try:
        s3_client: S3Client = request.app.state.s3_clients[location_name]
    except KeyError:
        raise HTTPException(404, "Location not found")

    data_stream = s3_client.get_raw_object(key)
    return StreamingResponse(content=data_stream.iter_chunks())


@proxies_router.get(
    "/plot_image/{location_name}/{camera_name}/{group_name}/{filename}",
    response_class=StreamingResponse,
    name="plot_image",
)
def proxy_plot_image(
    location_name: str,
    camera_name: str,
    group_name: str,
    filename: str,
    request: Request,
) -> StreamingResponse:
    # auxtel_night_report_2023-08-16_Coverage_airmass

    try:
        to_remove = "_".join((camera_name, "night_report")) + "_"
        rest = filename.replace(to_remove, "")
        date_str = rest.split("_")[0]
        burn, ext = rest.split(".")
    except ValueError:
        raise HTTPException(404, "Filename not valid.")
    key = f"{camera_name}/{date_str}/night_report/{group_name}/{filename}"
    try:
        s3_client: S3Client = request.app.state.s3_clients[location_name]
    except KeyError:
        raise HTTPException(404, "Location not found.")
    data_stream = s3_client.get_raw_object(key)
    return StreamingResponse(content=data_stream.iter_chunks())


@proxies_router.get(
    "/event_video/{location_name}/{camera_name}/{channel_name}/{filename}",
    response_class=StreamingResponse,
    name="event_video",
)
def proxy_video(
    location_name: str,
    camera_name: str,
    channel_name: str,
    filename: str,
    request: Request,
    range: str = Header(None),  # Get the Range header from the request
) -> StreamingResponse:
    try:
        to_remove = "_".join((camera_name, channel_name)) + "_"
        rest = filename.replace(to_remove, "")
        date_str, seq_ext = rest.split("_")
        seq_str, ext = seq_ext.split(".")
    except ValueError:
        raise HTTPException(404, "Filename not valid.")

    key = f"{camera_name}/{date_str}/{channel_name}/{seq_str}/{filename}"

    try:
        s3_client: S3Client = request.app.state.s3_clients[location_name]
    except KeyError:
        raise HTTPException(404, "Location not found.")

    s3_request_headers = {}
    if range:
        logger.info("Headers:", range=range)
        byte_range = range.split("=")[1]
        s3_request_headers["Range"] = f"bytes={byte_range}"

    data = s3_client.get_movie(key, s3_request_headers)
    if "Body" in data and "ResponseMetadata" in data:
        video = data["Body"]
        headers = data["ResponseMetadata"]["HTTPHeaders"]
        headers["content-type"] = "video/mp4"
    else:
        raise HTTPException(404, "No data found.")

    logger.info("Movie headers returned:", headers=headers)

    return StreamingResponse(
        content=video.iter_chunks(),
        headers=headers,
        status_code=206 if range else 200,
    )
