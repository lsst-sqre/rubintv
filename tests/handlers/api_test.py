import pytest
from httpx import AsyncClient

from rubintv.models.helpers import find_first
from rubintv.models.models import Camera, Location, get_current_day_obs
from rubintv.models.models_init import ModelsInitiator

m = ModelsInitiator()


@pytest.mark.asyncio
async def test_get_api_locations(client: AsyncClient) -> None:
    """Test that root api gives data for every location"""
    response = await client.get("/rubintv/api/")
    data = response.json()
    assert data == [loc.model_dump() for loc in m.locations]


@pytest.mark.asyncio
async def test_get_api_location(client: AsyncClient) -> None:
    """Test that api location gives data for a particular location"""
    location_name = "slac"
    location: Location | None = find_first(m.locations, "name", location_name)
    assert location is not None
    response = await client.get(f"/rubintv/api/{location_name}")
    data = response.json()
    assert data == location.model_dump()


@pytest.mark.asyncio
async def test_get_invalid_api_location(client: AsyncClient) -> None:
    """Test that api location returns 404 for a non-existent location"""
    location_name = "ramona"
    response = await client.get(f"/rubintv/api/{location_name}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_api_location_camera(client: AsyncClient) -> None:
    """Test that api location camera gives data for a particular camera"""
    location_name = "slac"
    camera_name = "slac_ts8"
    location: Location | None = find_first(m.locations, "name", location_name)
    assert location is not None
    cameras = location.cameras
    camera: Camera | None = find_first(cameras, "name", camera_name)
    assert camera is not None
    response = await client.get(f"/rubintv/api/{location_name}/{camera_name}")
    data = response.json()
    assert data == [location.model_dump(), camera.model_dump()]


@pytest.mark.asyncio
async def test_get_invalid_api_location_camera(client: AsyncClient) -> None:
    """Test that api location returns 404 for a camera not at an existing
    location"""
    location_name = "summit"
    camera_name = "ts8"
    response = await client.get(f"/rubintv/api/{location_name}/{camera_name}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_api_location_camera_current_for_offline(
    client: AsyncClient,
) -> None:
    """Test that api location camera current gives no events for offline
    camera"""
    location_name = "summit"
    camera_name = "lsstcam"

    response = await client.get(
        f"/rubintv/api/{location_name}/{camera_name}/current"
    )
    data = response.json()
    assert "date" in data
    assert data["date"] == get_current_day_obs().isoformat()
    assert "channel_events" in data
    assert data["channel_events"] == {}


@pytest.mark.asyncio
async def test_get_api_camera_for_date(client: AsyncClient) -> None:
    """Test that api location/camera/current day obs yields a result"""
    today = get_current_day_obs()
    response = await client.get(f"/rubintv/api/slac/slac_ts8/date/{today}")
    data = response.json()
    print(f"data is: {data}")
    assert (
        data["channel_events"]["focal_plane_mosaic"][0]["key"]
        == f"slac_ts8/{today}/focal_plane_mosaic/000000/mocked_event.jpg"
    )