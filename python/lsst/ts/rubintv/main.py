"""The main application factory for the rubintv service.

Notes
-----
Be aware that, following the normal pattern for FastAPI services, the app is
constructed when this module is loaded and is not deferred until a function is
called.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# from safir.dependencies.http_client import http_client_dependency
# from safir.logging import configure_logging, configure_uvicorn_logging
from safir.middleware.x_forwarded import XForwardedMiddleware

from . import __version__
from .background.currentpoller import CurrentPoller
from .background.historicaldata import HistoricalPoller
from .config import config
from .handlers.api import api_router
from .handlers.ddv_routes_handler import ddv_router
from .handlers.ddv_websocket_handler import ddv_client_ws_router, internal_ws_router
from .handlers.heartbeat_server import heartbeat_ws_router
from .handlers.internal import internal_router
from .handlers.pages import pages_router
from .handlers.proxies import proxies_router
from .handlers.websocket import data_ws_router
from .handlers.websockets_clients import clients
from .models.models_init import ModelsInitiator
from .s3client import S3Client

__all__ = ["app", "config"]


# configure_logging(
#     profile=config.profile,
#     log_level=config.log_level,
#     name=config.name,
# )
# configure_uvicorn_logging(config.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # Initialise model data fixtures
    models = ModelsInitiator()

    # initialise the background bucket pollers
    cp = CurrentPoller(models.locations)
    hp = HistoricalPoller(models.locations)

    # inject app state
    app.state.models = models
    app.state.current_poller = cp
    app.state.historical = hp
    app.state.s3_clients = {}
    for location in models.locations:
        app.state.s3_clients[location.name] = S3Client(
            location.profile_name, location.bucket_name
        )

    # start polling buckets for data
    today_polling = asyncio.create_task(cp.poll_buckets_for_todays_data())
    historical_polling = asyncio.create_task(hp.check_for_new_day())

    yield

    historical_polling.cancel()
    today_polling.cancel()
    for c in clients.values():
        await c.close()
    # await http_client_dependency.aclose()


def create_app() -> FastAPI:
    """The main FastAPI application for rubintv."""
    app = FastAPI(
        title=config.name,
        description="rubinTV is a Web app to display Butler-served data sets",
        version=__version__,
        openapi_url=f"{config.path_prefix}/openapi.json",
        docs_url=f"{config.path_prefix}/docs",
        redoc_url=f"{config.path_prefix}/redoc",
        debug=True,
        lifespan=lifespan,
    )

    # Intwine webpack assets
    # generated with npm run build
    if os.path.isdir("assets"):
        app.mount(
            f"{config.path_prefix}/static/assets",
            StaticFiles(directory="assets"),
            name="static-assets",
        )

    # Intwine jinja2 templating
    app.mount(
        f"{config.path_prefix}/static",
        StaticFiles(directory=Path(__file__).parent / "static"),
        name="static",
    )

    external_ws_router_prefix = f"{config.path_prefix}/ws"

    # Mount Derived Data Visualization Flutter app.
    ddv_app_root = "ddv/build/web"
    if os.path.isdir(ddv_app_root):
        app.mount(
            f"{config.path_prefix}/ddv",
            StaticFiles(directory=ddv_app_root, html=True),
            name="ddv-flutter",
        )
        app.state.ddv_path = ddv_app_root
        # Attach DDV Flutter client websocket (external):
        app.include_router(
            ddv_client_ws_router, prefix=f"{external_ws_router_prefix}/ddv"
        )
        # Provide router that hooks up ddv/index.html
        app.include_router(ddv_router, prefix=f"{config.path_prefix}/ddv")

    # Attach the routers.

    # Internal routing:
    app.include_router(internal_router)
    # Below includes DDV worker pod websocket (internal):
    app.include_router(internal_ws_router, prefix="/ws")

    # External websocket routing:
    app.include_router(data_ws_router, prefix=f"{external_ws_router_prefix}/data")
    app.include_router(
        heartbeat_ws_router, prefix=f"{external_ws_router_prefix}/heartbeats"
    )

    # External HTTP routing:
    app.include_router(api_router, prefix=f"{config.path_prefix}/api")
    app.include_router(proxies_router, prefix=f"{config.path_prefix}")
    app.include_router(pages_router, prefix=f"{config.path_prefix}")

    # Add middleware.
    app.add_middleware(XForwardedMiddleware)

    return app


app = create_app()
