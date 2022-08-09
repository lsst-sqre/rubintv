"""The main application factory for the rubintv service."""

__all__ = ["create_app", "get_current_day_obs"]

import datetime
from datetime import timedelta
from pathlib import Path
from typing import Dict, List

import aiohttp_jinja2
import jinja2
from aiohttp import web
from dateutil.tz import gettz
from google.cloud import storage
from google.cloud.storage import Bucket
from safir.http import init_http_session
from safir.logging import configure_logging
from safir.metadata import setup_metadata
from safir.middleware import bind_logger

from rubintv.config import Configuration
from rubintv.handlers import init_external_routes, init_internal_routes
from rubintv.models import Camera, Event, cameras


def create_app() -> web.Application:
    """Create and configure the aiohttp.web application."""
    config = Configuration()
    configure_logging(
        profile=config.profile,
        log_level=config.log_level,
        name=config.logger_name,
    )

    root_app = web.Application()
    root_app["safir/config"] = config
    client = storage.Client.create_anonymous_client()
    bucket = client.bucket("rubintv_data")
    root_app["rubintv/gcs_bucket"] = bucket
    root_app["rubintv/historical_data"] = HistoricalData(bucket)
    root_app["rubintv/site_title"] = "RubinTV Display"
    setup_metadata(package_name="rubintv", app=root_app)
    setup_middleware(root_app)
    root_app.add_routes(init_internal_routes())
    root_app.cleanup_ctx.append(init_http_session)

    sub_app = web.Application()
    aiohttp_jinja2.setup(
        sub_app,
        loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
    )
    setup_middleware(sub_app)
    sub_app.add_routes(init_external_routes())
    sub_app.add_routes(
        [
            web.static(
                "/static",
                Path(__file__).parent / "static",
                name="static",
                append_version=True,
            ),
        ]
    )
    sub_app["static_root_url"] = "/rubintv/static"
    env = aiohttp_jinja2.get_env(sub_app)
    env.globals.update(
        zip=zip,
        url_for=web.Resource.url_for,
        autoescape=jinja2.select_autoescape(),
    )

    root_app.add_subapp(f'/{root_app["safir/config"].name}', sub_app)
    return root_app


def setup_middleware(app: web.Application) -> None:
    """Add middleware to the application."""
    app.middlewares.append(bind_logger)


def get_current_day_obs() -> datetime.date:
    """Get the current day_obs - the observatory rolls the date over at UTC-12"""
    utc = gettz("UTC")
    nowUtc = datetime.datetime.now().astimezone(utc)
    offset = timedelta(hours=-12)
    dayObs = (nowUtc + offset).date()
    return dayObs


class HistoricalData:
    """Provide a cache of the historical data.

    Provides a cache of the historical data which updates when the day rolls
    over, but means that the full blob contents can be looped over without
    making a request for the full data for each operation.
    """

    def __init__(self, bucket: Bucket) -> None:
        self._bucket = bucket
        self._events = {}
        self._events = self._get_events()
        self._lastCall = get_current_day_obs()

    def _get_blobs(self) -> List[Bucket]:
        blobs = []
        cameras_with_history = [
            cam for cam in cameras.values() if cam.has_historical
        ]
        for cam in cameras_with_history:
            for channel in cam.channels.values():
                prefix = channel.prefix
                print(f"Trying prefix: {prefix}")
                blobs += list(self._bucket.list_blobs(prefix=prefix))
                print(f"blobs found: {len(blobs)}")
        return blobs

    def _get_events(self) -> Dict[str, Dict[str, List[Event]]]:
        if not self._events or get_current_day_obs() > self._lastCall:
            blobs = self._get_blobs()
            self._events = self._sort_events_from_blobs(blobs)
            self._lastCall = get_current_day_obs()
        return self._events

    def _sort_events_from_blobs(
        self, blobs: List
    ) -> Dict[str, Dict[str, List[Event]]]:
        """Returns a dict of dicts: an outer with key per camera
        and the inner with a key per channel for that camera and a
        corresponding list of events for each channel
        """
        all_events = [
            Event(blob.public_url)
            for blob in blobs
            if list(filter(blob.public_url.endswith, [".png", ".jpg", ".mp4"]))
            != []
        ]
        s_events = sorted(
            all_events, key=lambda x: (x.date, x.seq), reverse=True
        )
        events_dict: Dict[str, Dict[str, List[Event]]] = {}
        cameras_with_history = [
            cam for cam in cameras.values() if cam.has_historical
        ]
        for cam in cameras_with_history:
            channels = cam.channels
            events_dict[cam.slug] = {}
            for channel in channels:
                events_dict[cam.slug][channel] = [
                    e for e in s_events if e.prefix == channels[channel].prefix
                ]
        return events_dict

    def get_years(self, camera: Camera) -> List[int]:
        camera_name = camera.slug
        years = set(
            [
                event.date.year
                for event in self._get_events()[camera_name]["monitor"]
            ]
        )
        return list(years)

    def get_months_for_year(self, camera: Camera, year: int) -> List[int]:
        camera_name = camera.slug
        months = set(
            [
                event.date.month
                for event in self._get_events()[camera_name]["monitor"]
                if event.date.year == year
            ]
        )
        reverse_months = sorted(months, reverse=True)
        return list(reverse_months)

    def get_days_for_month_and_year(
        self, camera: Camera, month: int, year: int
    ) -> Dict[int, int]:
        """Returns a dict:
        { day_num: num_events }
        """
        camera_name = camera.slug
        days = set(
            [
                event.date.day
                for event in self._get_events()[camera_name]["monitor"]
                if event.date.month == month and event.date.year == year
            ]
        )
        days_dict = {
            day: self.get_max_event_seq_for_date(
                camera, datetime.date(year, month, day)
            )
            for day in list(days)
        }
        return days_dict

    def get_max_event_seq_for_date(
        self, camera: Camera, a_date: datetime.date
    ) -> int:
        camera_name = camera.slug
        cam_events = self._get_events()[camera_name]["monitor"]
        days_events = [ev for ev in cam_events if ev.date.date() == a_date]
        return days_events[0].seq

    def get_events_for_date(
        self, camera: Camera, a_date: datetime.date
    ) -> Dict[str, List[Event]]:
        """returns dict of events:
        { 'chan_name1': [Event 1, Event 2, ...], 'chan_name2': [...], ...}
        """
        camera_name = camera.slug
        events_dict = self._get_events()[camera_name]
        days_events_dict = {}
        for channel in events_dict:
            days_events_dict[channel] = [
                event
                for event in events_dict[channel]
                if event.date.date() == a_date
            ]
        return days_events_dict

    def get_second_most_recent_day(self, camera: Camera) -> datetime.date:
        camera_name = camera.slug
        events = self._get_events()[camera_name]["monitor"]
        most_recent = events[0].date
        events = [event for event in events if not (event.date == most_recent)]
        if events:
            second_most = events[0].date.date()
            return second_most
        else:
            return most_recent.date()

    def get_most_recent_event(self, camera: Camera) -> Event:
        camera_name = camera.slug
        events = self._get_events()[camera_name]["monitor"]
        return events[0]
