import asyncio
import re
from datetime import date

import structlog

from rubintv.models.helpers import objects_to_events, objects_to_ngt_reports
from rubintv.models.models import (
    Camera,
    Channel,
    Event,
    Location,
    NightReport,
    get_current_day_obs,
)
from rubintv.s3client import S3Client


class HistoricalPoller:
    """Provide a cache of the historical data.

    Provides a cache of the historical data which updates when the day rolls
    over.
    """

    _clients: dict[str, S3Client] = {}

    _metadata: dict[str, list[dict[str, str]]] = {}
    _events: dict[str, list[Event]] = {}
    _nr_metadata: dict[str, list[NightReport]] = {}

    _camera_years: dict[str, dict[str, set[int]]] = {}

    # polling period in seconds
    CHECK_NEW_DAY_PERIOD = 60

    def __init__(self, locations: list[Location]) -> None:
        # locations = [locations[0]]
        self._locations = locations
        self._clients = {
            location.name: S3Client(location.bucket_name)
            for location in locations
        }

        self._have_downloaded = False
        self._last_reload = get_current_day_obs()

        self.cam_year_rgx = re.compile(r"(\w+)\/([\d]{4})-[\d]{2}-[\d]{2}")

    async def check_for_new_day(self) -> None:
        while True:
            if (
                self._last_reload > get_current_day_obs()
                or not self._have_downloaded
            ):
                for location in self._locations:
                    await self._refresh_location_store(location)

                self._last_reload = get_current_day_obs()
                self._have_downloaded = True
            else:
                await asyncio.sleep(self.CHECK_NEW_DAY_PERIOD)

    async def _refresh_location_store(self, location: Location) -> None:
        logger = structlog.get_logger(__name__)

        try:
            up_to_date_objects = await self._get_objects(location)
            await self.filter_convert_store_objects(
                up_to_date_objects, location
            )
        except Exception as e:
            logger.error(e)

    async def _get_objects(self, location: Location) -> list[dict[str, str]]:
        """Downloads objects from the bucket for each online camera for the
        location.

        Returns
        -------
        objects :  `list` [`dict` [`str`, `str`]]
            A list of dicts representing bucket objects.
        """
        logger = structlog.get_logger(__name__)

        objects = []
        for cam in location.cameras:
            if cam.online:
                logger.info(f"Listing objects for {location.name}/{cam.name}")
                try:
                    objects.extend(
                        self._clients[location.name].list_objects(
                            prefix=cam.name
                        )
                    )
                except Exception as e:
                    logger.error(e)
        return objects

    async def filter_convert_store_objects(
        self, objects: list[dict[str, str]], location: Location
    ) -> None:
        logger = structlog.get_logger(__name__)
        locname = location.name
        self._camera_years[locname] = await self.build_year_dict(objects)

        metadata_objs = [o for o in objects if "metadata.json" in o["key"]]
        n_report_objs = [o for o in objects if "night_report" in o["key"]]
        event_objs = [
            o
            for o in objects
            if not (o in metadata_objs or o in n_report_objs)
        ]

        self._metadata[locname] = metadata_objs
        self._nr_metadata[locname] = objects_to_ngt_reports(n_report_objs)
        logger.info(f"Building historical events for {locname}")
        self._events[locname] = objects_to_events(event_objs)

    async def build_year_dict(
        self, objects: list[dict[str, str]]
    ) -> dict[str, set[int]]:
        """
        Builds a dictionary of lists of years keyed by camera name.

        Returns:
            `dict` [`str`, `list` [`int`]]: A dictionary containing lists of
            years keyed by camera name.
        """
        year_dict: dict[str, set[int]] = {}
        for obj in objects:
            cam_name, year = await self.extract_cam_year(obj)
            if year is not None and cam_name is not None:
                if cam_name not in year_dict:
                    year_dict[cam_name] = set()
                year_dict[cam_name].add(year)
        return year_dict

    async def extract_cam_year(
        self, obj: dict[str, str]
    ) -> tuple[str | None, int | None]:
        if match := self.cam_year_rgx.match(obj["key"]):
            cam, year = match.groups()
            return cam, int(year)
        else:
            return None, None

    async def get_night_reports_for(
        self, location: Location, camera: Camera, date_str: str
    ) -> list[NightReport]:
        """Returns a list of Night Reports Event objects for the camera and
        date.

        Parameters
        ----------
        camera : `Camera`
            The given Camera.
        obs_date : `date`
            The given date.

        Returns
        -------
        reports : `List` [`NightReport`]
            A list of Night Reports.
        """
        reports = [
            report
            for report in self._nr_metadata[location.name]
            if report.camera == camera.name and report.day_obs == date_str
        ]
        return reports

    def get_years(self, location: Location, camera: Camera) -> list[int]:
        """Returns a list of years for a given Camera in which there are Events
        in the bucket.

        Parameters
        ----------
        camera : `Camera`
            The given Camera.

        Returns
        -------
        years : `list` [`int`]
            A sorted list of years as integers.
        """
        return sorted(list(self._camera_years[location.name][camera.name]))

    def get_months_for_year(
        self, location: Location, camera: Camera, year: int
    ) -> list[int]:
        """Returns a list of months for the given Camera and year
        for which there are Events in the bucket.

        Parameters
        ----------
        camera : `Camera`
            The given Camera.
        year : `int`
            The given year.

        Returns
        -------
        months : `list` [`int`]
            List of month numbers (1..12 inclusive).
        """
        months = set(
            [
                event.day_obs_date().month
                for event in self._events[location.name]
                if (event.day_obs_date().year == year)
                and (event.camera_name == camera.name)
            ]
        )
        reverse_months = sorted(months, reverse=True)
        return list(reverse_months)

    def get_days_for_month_and_year(
        self, location: Location, camera: Camera, month: int, year: int
    ) -> list[tuple[int, int | str]]:
        """Given a Camera, year and number of month, returns a list of tuples
        of each day that has a record of Events paired with the max seq_num for
        that day.

        Parameters
        ----------
        camera : `Camera`
            The given Camera.
        month : `int`
            The given month (1...12)
        year : `int`
            The given year.

        Returns
        -------
        day_and_seqmax_list : `list` [`tuple` [`int`, `int` | `str`]]
            A dict with day number for key and last seq_num for that day as
            value.
        """

        month_str = "{:02}".format(month)
        days = set(
            [
                event.day_obs_date().day
                for event in self._events[location.name]
                if event.day_obs.startswith(f"{year}-{month_str}-")
                and event.camera_name == camera.name
            ]
        )
        day_and_seqmax_list = [
            (
                day,
                self.get_max_seq_for_date(
                    location, camera, date(year, month, day)
                ),
            )
            for day in sorted(list(days))
        ]
        return day_and_seqmax_list

    def get_max_seq_for_date(
        self, location: Location, camera: Camera, a_date: date
    ) -> int | str:
        """Takes a Camera and date and returns the max sequence number
        for Events recorded on that date.

        Parameters
        ----------
        camera : `Camera`
            The given Camera.
        date_str : `str`
            The given date as a `Datetime.date`.

        Returns
        -------
        seq_num : `int | str`
            The seq_num of the last Event for that Camera and day. In All Sky's
            case, the max_seq can be the string ``"final"``.
        """
        date_str = f"{a_date}"
        events = [
            e
            for e in self._events[location.name]
            if e.camera_name == camera.name and e.day_obs == date_str
        ]
        max_seq = max(events, key=lambda e: e.seq_num).seq_num
        return max_seq

    def get_events_for_date(
        self, location: Location, camera: Camera, date_str: str
    ) -> dict[str, list[Event]]:
        """Given camera and date, returns a dict of list of events, keyed
        by channel name.

        Parameters
        ----------
        camera : `Camera`
            The given Camera object.

        date_str: `str`
            The date to find Events for.

        Returns
        -------
        days_events_dict : `dict` [`str`, `list` [`Event`]]

        Example
        -------
        Return values are in the format:
        ``{ 'chan_name1': [Event 1, Event 2, ...], 'chan_name2': [...], ...}``.
        """

        days_events_dict = {}
        if camera.channels:
            for channel in camera.channels:
                days_events_dict[channel.name] = [
                    event
                    for event in self._events[location.name]
                    if event.camera_name == camera.name
                    and event.day_obs == date_str
                    and event.channel_name == channel.name
                ]
        return days_events_dict

    async def get_most_recent_day(
        self, location: Location, camera: Camera
    ) -> str:
        """Returns most recent day for which there is data in the bucket for
        the given Camera.

        Parameters
        ----------

        camera : `Camera`
            The given Camera object.

        Returns
        -------

        most_recent : `str`
            The date of the most recent day's Event in the form
            ``"YYYY-MM-DD"``.
        """
        events = [
            event
            for event in self._events[location.name]
            if event.camera_name == camera.name
        ]
        most_recent = events.pop().day_obs
        return most_recent

    async def get_most_recent_event(
        self, location: Location, camera: Camera, channel: Channel
    ) -> Event:
        """Returns most recent Event for the given Camera.

        Parameters
        ----------
        camera : `Camera`
            The given Camera object.

        channel : `Channel`
            A Channel of the given camera.

        Returns
        -------
        event : `Event`
            The most recent Event for the given Camera

        """
        events = [
            event
            for event in self._events[location.name]
            if event.camera_name == camera.name
            and event.channel_name == channel.name
        ]
        return events.pop()

    async def get_camera_calendar(
        self, location: Location, camera: Camera
    ) -> dict[int, dict[int, list[tuple[int, int | str]]]]:
        """Returns a dict representing a calendar for the given Camera

        Provides a list of tuples for (days and max seq_num of Events), within
        a dict of months, within a dict keyed by year for the given Camera.

        Parameters
        ----------
        camera : `Camera`
            The given Camera object.

        Returns
        -------
        years : `dict` [`int`, `dict` [`int`, `list` [`tuple` [`int`, `int` |
        `str`]]]]
            A data structure for the view to iterate over with years, months,
            days and num. of events for that day for the given Camera.

        """
        active_years = self.get_years(location, camera)
        years = {}
        for year in active_years:
            months = self.get_months_for_year(location, camera, year)
            months_days = {
                month: self.get_days_for_month_and_year(
                    location, camera, month, year
                )
                for month in months
            }
            years[year] = months_days
        return years
