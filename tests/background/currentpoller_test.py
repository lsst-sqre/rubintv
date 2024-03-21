import asyncio
from typing import Any, Iterator
from unittest.mock import AsyncMock, patch

import pytest
from lsst.ts.rubintv.background.currentpoller import CurrentPoller
from lsst.ts.rubintv.models.models import Camera, Location
from lsst.ts.rubintv.models.models_helpers import find_first
from lsst.ts.rubintv.models.models_init import ModelsInitiator
from moto import mock_s3

from ..mockdata import RubinDataMocker

m = ModelsInitiator()


@pytest.fixture(scope="function")
def rubin_data_mocker(mock_s3_client: Any) -> Iterator[RubinDataMocker]:
    with mock_s3():
        mocker = RubinDataMocker(m.locations, s3_required=True)
        yield mocker


@pytest.fixture
def current_poller(rubin_data_mocker: RubinDataMocker) -> CurrentPoller:
    return CurrentPoller(m.locations)


@pytest.fixture(scope="function")
def c_poller_no_mock_data(rubin_data_mocker: RubinDataMocker) -> Any:
    with mock_s3():
        yield CurrentPoller(m.locations)


@pytest.mark.asyncio
async def test_poll_buckets_for_todays_data(
    current_poller: CurrentPoller, rubin_data_mocker: RubinDataMocker
) -> None:
    await current_poller.clear_all_data()
    # Mocking external functions
    with (
        patch(
            "lsst.ts.rubintv.models.models.get_current_day_obs", return_value="20210101"
        ) as mock_day_obs,
        patch(
            "lsst.ts.rubintv.background.currentpoller.CurrentPoller.clear_all_data",
            new_callable=AsyncMock,
        ),
        patch(
            "lsst.ts.rubintv.background.currentpoller.CurrentPoller.seive_out_metadata",
            new_callable=AsyncMock,
        ) as mock_metadata,
        patch(
            (
                "lsst.ts.rubintv.background.currentpoller.CurrentPoller."
                "seive_out_night_reports"
            ),
            new_callable=AsyncMock,
        ) as mock_night_reports,
        patch(
            "lsst.ts.rubintv.background.currentpoller.CurrentPoller."
            "process_channel_objects",
            new_callable=AsyncMock,
        ) as mock_process_objects,
    ):
        # Execute test
        try:
            # Run the method for a specified number of seconds, then timeout
            await asyncio.wait_for(
                current_poller.poll_buckets_for_todays_data(), timeout=0.2
            )
        except asyncio.TimeoutError:
            pass

        # Assertions
        assert mock_day_obs
        mock_metadata.assert_called()
        mock_night_reports.assert_called()
        mock_process_objects.assert_called()
        assert current_poller.completed_first_poll is True


@pytest.mark.asyncio
async def test_poll_buckets_for_today_process_and_store_seq_events(
    current_poller: CurrentPoller, rubin_data_mocker: RubinDataMocker
) -> None:
    await current_poller.clear_all_data()
    try:
        await asyncio.wait_for(
            current_poller.poll_buckets_for_todays_data(), timeout=0.2
        )
    except asyncio.TimeoutError:
        # The timeout error is expected
        pass

    mocked_objs_keys = rubin_data_mocker.channel_objs.keys()

    # make sure the keys for the location/cameras match up
    current_keys = sorted([k for k in current_poller._events.keys()])
    assert current_keys == sorted(mocked_objs_keys)

    # and that they have the right number of events
    for ck in current_keys:
        assert sorted(current_poller._events[ck]) == sorted(
            rubin_data_mocker.events[ck]
        )


@pytest.mark.asyncio
async def test_clear_all_data(current_poller: CurrentPoller) -> None:
    await current_poller.clear_all_data()
    try:
        await asyncio.wait_for(
            current_poller.poll_buckets_for_todays_data(), timeout=0.1
        )
    except asyncio.TimeoutError:
        pass
    await current_poller.clear_all_data()
    assert current_poller._objects == {}
    assert current_poller._events == {}
    assert current_poller._metadata == {}
    assert current_poller._table == {}
    assert current_poller._per_day == {}
    assert current_poller._most_recent_events == {}
    assert current_poller._nr_metadata == {}
    assert current_poller._nr_reports == {}


@pytest.mark.asyncio
async def test_process_channel_objects(
    c_poller_no_mock_data: CurrentPoller, rubin_data_mocker: RubinDataMocker
) -> None:
    current_poller = c_poller_no_mock_data
    await current_poller.clear_all_data()

    camera, location = await get_test_camera_and_location()
    loc_cam = f"{location.name}/{camera.name}"
    objects = rubin_data_mocker.channel_objs[loc_cam]

    with (
        patch(
            "lsst.ts.rubintv.background.currentpoller.CurrentPoller."
            "update_channel_events",
            new_callable=AsyncMock,
        ) as mock_update_channel_events,
        patch(
            "lsst.ts.rubintv.background.currentpoller.CurrentPoller.make_per_day_data",
            new_callable=AsyncMock,
        ) as mock_make_per_day_data,
        patch(
            "lsst.ts.rubintv.background.currentpoller." "notify_ws_clients",
        ) as mock_notify_ws_clients,
    ):
        await current_poller.process_channel_objects(objects, loc_cam, camera)

        expected_events = rubin_data_mocker.events[loc_cam]

        mock_update_channel_events.assert_called_once_with(
            expected_events, "base-usdf/fake_auxtel", camera
        )
        mock_make_per_day_data.assert_called()
        mock_notify_ws_clients.assert_called()


@pytest.mark.asyncio
async def test_update_channel_events(
    c_poller_no_mock_data: CurrentPoller, rubin_data_mocker: RubinDataMocker
) -> None:
    current_poller = c_poller_no_mock_data
    with (
        patch(
            "lsst.ts.rubintv.background.currentpoller." "notify_ws_clients",
        ) as mock_notify_ws_clients,
    ):
        camera, location = await get_test_camera_and_location()
        loc_cam = f"{location.name}/{camera.name}"
        events = rubin_data_mocker.events[loc_cam]

        await current_poller.clear_all_data()
        assert current_poller._most_recent_events == {}
        loc_cam = f"{location.name}/{camera.name}"
        await current_poller.update_channel_events(events, loc_cam, camera)
        assert current_poller._most_recent_events != {}
        mock_notify_ws_clients.assert_called()


async def get_test_camera_and_location() -> tuple[Camera, Location]:
    location: Location = find_first(m.locations, "name", "base-usdf")
    # fake_auxtel has both 'streaming' and per-day channels
    camera: Camera = find_first(location.cameras, "name", "fake_auxtel")
    return (camera, location)
