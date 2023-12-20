from datetime import date
from typing import Any, Iterable

import structlog

from rubintv.models.models import Camera, Channel, Event, NightReport

__all__ = [
    "find_first",
    "find_all",
    "string_int_to_date",
    "date_str_to_date",
    "objects_to_events",
    "objects_to_ngt_reports",
]


def find_first(a_list: list[Any], key: str, to_match: str) -> Any | None:
    result = None
    if iterator := _find_by_key_and_value(a_list, key, to_match):
        try:
            result = next(iter(iterator))
        except StopIteration:
            pass
    return result


def find_all(a_list: list[Any], key: str, to_match: str) -> list[Any] | None:
    result = None
    if iterator := _find_by_key_and_value(a_list, key, to_match):
        result = list(iterator)
    return result


def _find_by_key_and_value(
    a_list: list[Any], key: str, to_match: str
) -> Iterable[Any] | None:
    result = None
    if not a_list:
        return None
    try:
        result = (o for o in a_list if o.model_dump()[key] == to_match)
    except IndexError:
        pass
    return result


def date_str_to_date(date_string: str) -> date:
    y, m, d = date_string.split("-")
    return date(int(y), int(m), int(d))


def string_int_to_date(date_string: str) -> date:
    """Returns a date object from a given date string in the
    form ``"YYYYMMDD"``.

    Parameters
    ----------
    date_string : `str`
        A date string in the form ``"YYYYMMDD"``.

    Returns
    -------
    `date`
        A date.
    """
    d = date_string
    return date(int(d[0:4]), int(d[4:6]), int(d[6:8]))


def objects_to_events(objects: list[dict]) -> list[Event]:
    logger = structlog.get_logger(__name__)
    events = []
    for object in objects:
        try:
            event = Event(**object)
            events.append(event)
        except ValueError as e:
            logger.info(e)
    return events


def objects_to_ngt_reports(objects: list[dict]) -> list[NightReport]:
    logger = structlog.get_logger(__name__)
    night_reports = []
    for object in objects:
        try:
            event = NightReport(**object)
            night_reports.append(event)
        except ValueError as e:
            logger.info(e)
    return night_reports


async def event_list_to_channel_keyed_dict(
    event_list: list[Event], channels: list[Channel]
) -> dict[str, list[Event]]:
    days_events_dict = {}
    for channel in channels:
        days_events_dict[channel.name] = [
            event for event in event_list if event.channel_name == channel.name
        ]
    return days_events_dict


def get_image_viewer_link(camera: Camera, day_obs: date, seq_num: int) -> str:
    """Returns the url for the camera's external image viewer for a given date
    and seq num.

    Used in the template.

    Parameters
    ----------
    camera : `Camera`
        The given camera.
    day_obs : `date`
        The given date.
    seq_num : `int`
        The given seq num.

    Returns
    -------
    url : `str`
        The url for the image viewer for a single image.
    """
    date_int_str = day_obs.isoformat().replace("-", "")
    url = camera.image_viewer_link.format(
        day_obs=date_int_str, seq_num=seq_num
    )
    return url
