"""Test fixtures for rubintv tests."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Tuple

import boto3
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from lsst.ts.rubintv.main import create_app
from lsst.ts.rubintv.models.models_init import ModelsInitiator
from moto import mock_aws

from .mockdata import RubinDataMocker


@pytest.fixture(scope="module")
def aws_credentials() -> None:
    """Mocked AWS Credentials for moto."""
    moto_credentials_file_path = (
        Path(__file__).parent.absolute() / "dummy_aws_credentials"
    )
    print(f"Credentials file path: {moto_credentials_file_path}")
    os.environ["AWS_SHARED_CREDENTIALS_FILE"] = str(moto_credentials_file_path)


@pytest_asyncio.fixture(scope="function")
async def mocked_app(
    aws_credentials: Any,
) -> AsyncIterator[Tuple[FastAPI, RubinDataMocker]]:
    with mock_s3_service():
        models = ModelsInitiator()
        mocker = RubinDataMocker(models.locations, s3_required=True)
        app = create_app()
        async with LifespanManager(app):
            yield app, mocker
        mocker.cleanup()


@pytest_asyncio.fixture(scope="function")
async def mocked_client(
    mocked_app: Tuple[FastAPI, RubinDataMocker]
) -> AsyncIterator[Tuple[AsyncClient, RubinDataMocker]]:
    app, mocker = mocked_app
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000/"
    ) as client:
        yield client, mocker


@pytest.fixture(scope="function")
def mock_s3_client(aws_credentials: Any) -> Any:
    with mock_s3_service():
        yield boto3.client("s3", region_name="us-east-1")


@contextmanager
def mock_s3_service() -> Any:
    mock = mock_aws()
    mock.start()
    try:
        yield
    finally:
        mock.stop()
