"""What the HTTP layer holds for the life of the process."""

from dataclasses import dataclass

import anyio

from scenewise.app.delivery import DeliveryPolicy
from scenewise.app.deps import Dependencies
from scenewise.service.config import Settings
from scenewise.service.http.health import Watchdog


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceState:
    """Built once in the lifespan; read by every request."""

    settings: Settings
    deps: Dependencies
    policy: DeliveryPolicy
    limiter: anyio.CapacityLimiter
    watchdog: Watchdog
