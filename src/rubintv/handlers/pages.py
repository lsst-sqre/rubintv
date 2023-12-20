"""Handlers for the app's external root, ``/rubintv/``."""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from safir.dependencies.logger import logger_dependency
from structlog.stdlib import BoundLogger

from rubintv.handlers.api import (
    get_camera_current_events,
    get_current_channel_event,
    get_location,
    get_location_camera,
    get_most_recent_historical_data,
    get_specific_channel_event,
)
from rubintv.handlers.pages_helpers import make_table_rows_from_columns_by_seq
from rubintv.models.helpers import find_first
from rubintv.models.models import Channel
from rubintv.s3client import S3Client
from rubintv.templates_init import get_templates

__all__ = ["get_home", "pages_router", "templates"]

pages_router = APIRouter()
"""FastAPI router for all external handlers."""

templates = get_templates()
"""Jinja2 for templating."""


@pages_router.get("/", response_class=HTMLResponse, name="home")
async def get_home(
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
) -> Response:
    """GET ``/rubintv/`` (the app's external root)."""
    logger.info("Request for the app home page")
    locations = request.app.state.models.locations
    return templates.TemplateResponse(
        "home.jinja", {"request": request, "locations": locations}
    )


@pages_router.get(
    "/event_image/{location_name}/{filename}",
    response_class=StreamingResponse,
    name="event_image",
)
def proxy_image(
    location_name: str,
    filename: str,
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
) -> StreamingResponse:
    try:
        camera_name, channel_name, date_str, seq_ext = filename.split("_")
        seq_str, ext = seq_ext.split(".")
    except ValueError:
        raise HTTPException(404, "Filename not valid.")
    key = f"{camera_name}/{date_str}/{channel_name}/{seq_str}/{filename}"
    s3_client: S3Client = request.app.state.s3_clients[location_name]
    data_stream = s3_client.get_raw_object(key)
    return StreamingResponse(content=data_stream.iter_chunks())


@pages_router.get(
    "/event_video/{location_name}/{filename}",
    response_class=StreamingResponse,
    name="event_video",
)
def proxy_video(
    location_name: str,
    filename: str,
    request: Request,
    range: Annotated[str | None, Header()] = None,
    logger: BoundLogger = Depends(logger_dependency),
) -> StreamingResponse:
    try:
        camera_name, channel_name, date_str, seq_ext = filename.split("_")
        seq_str, ext = seq_ext.split(".")
    except ValueError:
        raise HTTPException(404, "Filename not valid.")
    key = f"{camera_name}/{date_str}/{channel_name}/{seq_str}/{filename}"
    s3_client: S3Client = request.app.state.s3_clients[location_name]
    video = s3_client.get_raw_object(key)
    return StreamingResponse(
        content=video.iter_chunks(), status_code=206, media_type="video/mp4"
    )


@pages_router.get(
    "/{location_name}", response_class=HTMLResponse, name="location"
)
async def get_location_page(
    location_name: str,
    request: Request,
) -> Response:
    location = await get_location(location_name, request)
    return templates.TemplateResponse(
        "location.jinja", {"request": request, "location": location}
    )


@pages_router.get(
    "/{location_name}/{camera_name}",
    response_class=HTMLResponse,
    name="camera",
)
async def get_camera_page(
    location_name: str,
    camera_name: str,
    request: Request,
) -> Response:
    location, camera = await get_location_camera(
        location_name, camera_name, request
    )
    historical_busy = False
    day_obs: date | None = None
    table = {}
    try:
        event_data = await get_camera_current_events(
            location_name, camera_name, request
        )
        day_obs = event_data["date"]
        table = make_table_rows_from_columns_by_seq(
            event_data, camera.channels
        )
    except HTTPException:
        historical_busy = True

    template = "camera"
    if not camera.online:
        template = "not_online"

    return templates.TemplateResponse(
        f"{template}.jinja",
        {
            "request": request,
            "location": location,
            "camera": camera,
            "camera_json": camera.model_dump(),
            "table": table,
            "date": day_obs,
            "historical_busy": historical_busy,
        },
    )


@pages_router.get(
    "/{location_name}/{camera_name}/event",
    response_class=HTMLResponse,
    name="single_event",
)
async def get_specific_channel_event_page(
    location_name: str,
    camera_name: str,
    key: str,
    request: Request,
) -> Response:
    location, camera = await get_location_camera(
        location_name, camera_name, request
    )
    event = await get_specific_channel_event(
        location_name, camera_name, key, request
    )
    channel: Channel | None = None
    if event:
        channel = find_first(camera.channels, "name", event.channel_name)
    return templates.TemplateResponse(
        "single_event.jinja",
        {
            "request": request,
            "location": location,
            "camera": camera,
            "channel": channel,
            "event": event,
        },
    )


@pages_router.get(
    "/{location_name}/{camera_name}/current/{channel_name}",
    response_class=HTMLResponse,
    name="current_event",
)
async def get_current_channel_event_page(
    location_name: str, camera_name: str, channel_name: str, request: Request
) -> Response:
    location, camera = await get_location_camera(
        location_name, camera_name, request
    )
    event = await get_current_channel_event(
        location_name, camera_name, channel_name, request
    )
    channel: Channel | None = None
    if event:
        channel = find_first(camera.channels, "name", event.channel_name)
    return templates.TemplateResponse(
        "current_event.jinja",
        {
            "request": request,
            "location": location,
            "camera": camera,
            "channel": channel,
            "event": event,
        },
    )


@pages_router.get(
    "/{location_name}/{camera_name}/historical",
    response_class=HTMLResponse,
    name="historical",
)
async def get_historical_camera_page(
    location_name: str, camera_name: str, request: Request
) -> Response:
    location, camera = await get_location_camera(
        location_name, camera_name, request
    )
    historical_busy = False
    table = {}
    try:
        (day_obs, events, md) = await get_most_recent_historical_data(
            location, camera, request
        )
        event_data: dict = {
            "date": day_obs,
            "channel_events": events,
            "metadata": md,
        }
        table = make_table_rows_from_columns_by_seq(
            event_data, camera.channels
        )
    except HTTPException:
        historical_busy = True
    return templates.TemplateResponse(
        "historical.jinja",
        {
            "request": request,
            "location": location,
            "camera": camera,
            "camera_json": camera.model_dump(),
            "table": table,
            "date": day_obs,
            "historical_busy": historical_busy,
        },
    )
