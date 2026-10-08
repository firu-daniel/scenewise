"""``create_app()``: the FastAPI application and its lifespan.

Run it with ``uvicorn --factory scenewise.service.http.app:create_app``.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI

from scenewise import __version__
from scenewise.app.delivery import DeliveryPolicy
from scenewise.domain.time import Seconds
from scenewise.service import logs
from scenewise.service.bootstrap import build_dependencies
from scenewise.service.config import Settings
from scenewise.service.http.health import Watchdog
from scenewise.service.http.routes import router
from scenewise.service.http.state import ServiceState


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app; dependencies are built once, in the lifespan."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved = settings or Settings()
        logs.configure(resolved.log)
        service = resolved.service
        app.state.scenewise = ServiceState(
            settings=resolved,
            deps=build_dependencies(resolved),
            policy=DeliveryPolicy(
                state_prefix=service.state_prefix,
                attempt_budget=Seconds(service.attempt_budget_s),
            ),
            limiter=anyio.CapacityLimiter(service.max_jobs),
            watchdog=Watchdog(
                limit_s=service.attempt_budget_s + service.watchdog_grace_s
            ),
        )
        yield

    app = FastAPI(title="scenewise", version=__version__, lifespan=lifespan)
    app.include_router(router)
    return app
