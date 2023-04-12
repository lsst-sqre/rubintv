import json
import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from aiohttp import web
from google.api_core.exceptions import NotFound
from google.cloud.storage.client import Blob, Bucket

from rubintv.models.historicaldata import HistoricalData, get_current_day_obs
from rubintv.models.models import (
    Camera,
    Channel,
    Event,
    Location,
    Night_Report_Event,
)
from rubintv.models.models_helpers import get_prefix_from_date

__all__ = [
    "get_image_viewer_link",
    "get_event_page_link",
    "date_from_url_part",
    "find_location",
    "get_per_day_channels",
    "get_channel_resource_url",
    "get_metadata_json",
    "month_names",
    "build_dict_with_remaining_channels",
    "make_table_rows_from_columns_by_seq",
    "get_most_recent_day_events",
    "get_sorted_events_from_blobs",
    "get_events_for_prefix_and_date",
    "get_current_event",
    "get_heartbeats",
    "build_title",
    "get_nights_report_link_type",
    "get_night_report_events",
    "get_historical_night_report_events",
]


def date_from_hyphenated_string(date_str: str) -> date:
    """Return a date from a date string.

    Parameters
    ----------
    date_str : str
        A string in the form ``"YYYY-MM-DD"``.

    Returns
    -------
    date
        A date object.
    """
    year, month, day = [int(s) for s in date_str.split("-")]
    the_date = date(year, month, day)
    return the_date


def date_from_url_part(url_part: str) -> date:
    """Return a date from a given string url segment.

    The url part must be a valid date in the form ``"YYYY-MM-DD"`` or an
    HTTPNotFound error will be thrown.

    Parameters
    ----------
    url_part : `str`
        A valid date in the form ``"YYYY-MM-DD"``.

    Returns
    -------
    the_date : `date`
        A date object.

    Raises
    ------
    web.HTTPNotFound
        The error 404 as the app response.
    """
    try:
        the_date = date_from_hyphenated_string(url_part)
    except ValueError:
        raise web.HTTPNotFound()
    return the_date


def find_location(location_name: str, request: web.Request) -> Location:
    location_name = request.match_info["location"]
    locations = request.config_dict["rubintv/models"].locations
    try:
        location: Location = locations[location_name]
    except KeyError:
        raise web.HTTPNotFound()
    return location


def get_per_day_channels(
    bucket: Bucket, camera: Camera, the_date: date, logger: Any
) -> Dict[str, str]:
    """Builds a dict of per-day channels to display

    Takes a bucket, camera and a given date and returns a dict of per-day
    channels to be iterated over in the view.
    If there is nothing available for those channels, an empty dict is returned.

    Parameters
    ----------
    bucket : `Bucket`
        The app-wide Bucket instance

    camera : `Camera`
        The given Camera object

    the_date : `date`
        The datetime.date object for the given day

    logger : `Any`
        The app-wide logging object

    Returns
    -------
    per_day_channels : `dict[str, str]`
        The list of events, per channel

    """
    per_day_channels = {}
    for channel in camera.per_day_channels.keys():
        if resource_url := get_channel_resource_url(
            bucket, camera.per_day_channels[channel], the_date, logger
        ):
            per_day_channels[channel] = resource_url
    return per_day_channels


def get_channel_resource_url(
    bucket: Bucket, channel: Channel, a_date: date, logger: Any
) -> str:
    date_str = a_date.strftime("%Y%m%d")
    prefix = f"{channel.prefix}/dayObs_{date_str}"
    url = ""
    if blobs := list(bucket.list_blobs(prefix=prefix)):
        url = blobs[0].public_url
    return url


def get_metadata_json(bucket: Bucket, camera: Camera, a_date: date) -> Dict:
    date_str = date_without_hyphens(a_date)
    blob_name = f"{camera.metadata_slug}_metadata/dayObs_{date_str}.json"
    metadata_json = "{}"
    if blob := bucket.get_blob(blob_name):
        metadata_json = blob.download_as_bytes()
    return json.loads(metadata_json)


def month_names() -> List[str]:
    return [date(2000, m, 1).strftime("%B") for m in list(range(1, 13))]


def build_dict_with_remaining_channels(
    bucket: Bucket,
    camera: Camera,
    events_dict: Dict[str, list[Event]],
    the_date: date,
) -> Dict[str, list[Event]]:
    # creates a dict where key => list of events e.g.:
    # {"monitor": [Event 1, Event 2 ...] , "im": [Event 2 ...] ... }
    primary_channel = list(camera.channels)[0]
    for chan in camera.channels:
        if chan == primary_channel:
            continue
        prefix = camera.channels[chan].prefix
        new_prefix = get_prefix_from_date(prefix, the_date)
        blobs = list(bucket.list_blobs(prefix=new_prefix))
        events_dict[chan] = get_sorted_events_from_blobs(blobs)
    return events_dict


def make_table_rows_from_columns_by_seq(
    events_dict: Dict, metadata: Dict
) -> Dict[int, dict[str, Event]]:
    d: Dict[int, dict[str, Event]] = {}
    # d == {seq: {chan1: event, chan2: event, ... }}
    for chan in events_dict:
        chan_events = events_dict[chan]
        for e in chan_events:
            if e.seq in d:
                d[e.seq].update({chan: e})
            else:
                d.update({e.seq: {chan: e}})
    # add an empty row for sequence numbers found only in metadata
    for seq_str in metadata:
        seq = int(seq_str)
        if seq not in d:
            d[seq] = {}
    # make sure the table is in order
    d = {k: v for k, v in sorted(d.items(), reverse=True)}
    return d


def get_most_recent_day_events(
    bucket: Bucket, camera: Camera, historical: HistoricalData
) -> tuple[date, dict[int, dict[str, Event]]]:
    obs_date = get_current_day_obs()
    metadata = get_metadata_json(bucket, camera, obs_date)
    events = {}
    for channel in camera.channels:
        prefix = camera.channels[channel].prefix
        events_found = get_events_for_prefix_and_date(prefix, obs_date, bucket)
        if events_found:
            events[channel] = events_found
            the_date = obs_date
    if not events:
        the_date = obs_date
        if not metadata:
            the_date = historical.get_most_recent_day(camera)
            events = historical.get_events_for_date(camera, the_date)
            metadata = get_metadata_json(bucket, camera, the_date)

    todays_events = make_table_rows_from_columns_by_seq(events, metadata)
    return (the_date, todays_events)


def get_sorted_events_from_blobs(blobs: List) -> List[Event]:
    events = [
        Event(el.public_url)
        for el in blobs
        if el.public_url.endswith(".png")
        or el.public_url.endswith(".jpg")
        or el.public_url.endswith(".mp4")
    ]
    sevents = sorted(events, key=lambda x: (x.obs_date, x.seq), reverse=True)
    return sevents


def get_events_for_prefix_and_date(
    prefix: str,
    the_date: date,
    bucket: Bucket,
) -> List[Event]:
    new_prefix = get_prefix_from_date(prefix, the_date)
    events = []
    blobs = list(bucket.list_blobs(prefix=new_prefix))
    if blobs:
        events = get_sorted_events_from_blobs(blobs)
    return events


def get_current_event(
    camera: Camera,
    channel: Channel,
    bucket: Bucket,
    historical: HistoricalData,
) -> Event:
    day_obs = get_current_day_obs()
    events = get_events_for_prefix_and_date(channel.prefix, day_obs, bucket)
    if events:
        latest = events[0]
    else:
        latest = historical.get_most_recent_event(camera, channel)
    return latest


def get_heartbeats(bucket: Bucket, prefix: str) -> List[Dict]:
    hb_blobs = list(bucket.list_blobs(prefix=prefix))
    heartbeats = []
    for hb_blob in hb_blobs:
        blob_content = None
        try:
            the_blob = bucket.blob(hb_blob.name)
            blob_content = the_blob.download_as_bytes()
        except NotFound:
            print(f"Error: {hb_blob.name} not found.")
        if not blob_content:
            continue
        else:
            hb = json.loads(blob_content)
            hb["url"] = hb_blob.name
            heartbeats.append(hb)
    return heartbeats


def build_title(*title_parts: str, request: web.Request) -> str:
    title = request.config_dict["rubintv/site_title"]
    to_append = " - ".join(title_parts)
    if to_append:
        title += " - " + to_append
    return title


def date_without_hyphens(a_date: date) -> str:
    return str(a_date).replace("-", "")


def get_image_viewer_link(day_obs: date, seq_num: int) -> str:
    date_str = date_without_hyphens(day_obs)
    url = (
        "http://ccs.lsst.org/FITSInfo/view.html?"
        f"image=AT_O_{date_str}_{seq_num:06}"
        "&raft=R00&color=grey&bias=Simple+Overscan+Correction"
        "&scale=Per-Segment&source=RubinTV"
    )
    return url


def get_event_page_link(
    location: Location,
    camera: Camera,
    channel: Channel,
    event: Event,
) -> str:
    return (
        f"{location.slug}/{camera.slug}/{channel.slug}/event/"
        f"{event.clean_date()}/{event.seq}"
    )


def get_historical_night_report_events(
    bucket: Bucket, reports_list: List[Night_Report_Event]
) -> Tuple[Dict[str, List[Night_Report_Event]], Dict[str, str]]:
    plots: Dict[str, List[Night_Report_Event]] = {}
    json_data = {}
    for r in reports_list:
        if r.file_ext == "json":
            blob = bucket.blob(r.blobname)
            json_raw_data = json.loads(blob.download_as_bytes())
            json_data = process_night_report_text_data(json_raw_data)
        else:
            if r.group in plots:
                plots[r.group].append(r)
            else:
                plots[r.group] = [r]
    return plots, json_data


def get_nights_report_link_type(
    bucket: Bucket, camera: Camera, the_date: date
) -> str:
    night_reports_link = ""
    if camera.night_report_prefix:
        if the_date == get_current_day_obs():
            night_reports_link = "current"
        elif get_night_report_events(bucket, camera, the_date):
            night_reports_link = "historic"
    return night_reports_link


def get_night_report_events(
    bucket: Bucket, camera: Camera, day_obs: date
) -> Optional[Tuple[Dict[str, List[Night_Report_Event]], Dict[str, str]]]:
    prefix = camera.night_report_prefix
    blobs = get_night_reports_blobs(bucket, prefix, day_obs)
    if not blobs:
        return None
    all_plots = []
    text_data = {}

    for blob in blobs:
        if blob.public_url.endswith(".json"):
            json_raw_data = json.loads(blob.download_as_bytes())
            text_data = process_night_report_text_data(json_raw_data)
        else:
            all_plots.append(
                Night_Report_Event(
                    blob.public_url, prefix, int(blob.time_created.timestamp())
                )
            )

    all_plots.sort(key=lambda ev: ev.name)
    plots: Dict[str, List[Night_Report_Event]] = {}
    for plot in all_plots:
        if plot.group in plots:
            plots[plot.group].append(plot)
        else:
            plots[plot.group] = [plot]

    return (plots, text_data)


def get_night_reports_blobs(
    bucket: Bucket, prefix: str, day_obs: date
) -> List[Blob]:
    date_str = date_without_hyphens(day_obs)
    prefix_with_date = "/".join([prefix, date_str])
    blobs = list(bucket.list_blobs(prefix=prefix_with_date))
    return blobs


def spaces_to_nbsps(match: re.Match) -> str:
    length = match.end() - match.start()
    result = "&nbsp;" * length
    return result


def crs_to_brs(match: re.Match) -> str:
    length = match.end() - match.start()
    result = "<br>" * length
    return result


def process_night_report_text_data(
    raw_data: Dict,
) -> Dict[str, Any]:
    text_part = [
        v for k, v in sorted(raw_data.items()) if k.startswith("text_")
    ]
    # match for two or more spaces
    ptrn = re.compile("[ ]{2,}")
    nb_text = [ptrn.sub(spaces_to_nbsps, line) for line in text_part]
    nb_br_text = [re.sub("\n\n", crs_to_brs, line) for line in nb_text]

    quantity = {k: v for k, v in raw_data.items() if v not in text_part}
    text = [line.split("\n") for line in nb_br_text]

    return {"text": text, "quantities": quantity}
