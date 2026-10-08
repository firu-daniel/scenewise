"""``Settings``: built once in the entry point and passed to ``bootstrap``.

Environment variables use the prefix ``SCENEWISE_`` and ``__`` between groups, e.g.
``SCENEWISE_SERVICE__MAX_JOBS=2``. Groups for back ends that do not exist yet (asr,
captions, llm, vision, labels, delivery) arrive with the features that read them.
"""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from scenewise.domain.jobs import StageName


def _default_state_prefix() -> str:
    return (Path.cwd() / ".scenewise" / "state").as_uri()


class _Group(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MediaSettings(_Group):
    """ffmpeg and ffprobe (names on PATH or absolute paths)."""

    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    min_major: PositiveInt = 6  # Ubuntu 24.04 ships 6.1


class InputSettings(_Group):
    """Where inputs may come from."""

    # file:// inputs are accepted only below these directories, and never below the
    # state prefix or an artifact root. Empty by default, so the HTTP service takes no
    # file:// input; the CLI adds the directory of the file it is given.
    local_roots: tuple[Path, ...] = ()


class ServiceSettings(_Group):
    """The push service and the job store (ARCHITECTURE.md §7)."""

    max_jobs: PositiveInt = 1
    max_body_bytes: PositiveInt = 1_048_576
    attempt_budget_s: PositiveInt = 1500
    watchdog_grace_s: PositiveInt = 120
    dispatch_deadline_s: PositiveInt = 1800
    lease_margin_s: PositiveInt = 120
    probe_period_s: PositiveInt = 10
    probe_failure_threshold: PositiveInt = 3
    max_attempts: PositiveInt = 5
    state_prefix: str = Field(default_factory=_default_state_prefix)
    # Directories a request's delivery.artifacts.uri_prefix may point into (besides the
    # state prefix's own job folders); artifacts always go to {uri_prefix}/{job_id}.
    artifact_roots: tuple[Path, ...] = ()
    required_stages: frozenset[StageName] = frozenset({StageName.AUDIO})

    @model_validator(mode="after")
    def _timing(self) -> Self:
        probe_window = self.probe_period_s * self.probe_failure_threshold
        total = self.attempt_budget_s + self.watchdog_grace_s + probe_window
        if total >= self.dispatch_deadline_s:
            msg = (
                f"attempt_budget_s + watchdog_grace_s + probe window = {total} s must "
                f"be < dispatch_deadline_s = {self.dispatch_deadline_s} s"
            )
            raise ValueError(msg)
        return self

    @property
    def lease_s(self) -> int:
        """The static lease: ``dispatch_deadline_s + lease_margin_s``."""
        return self.dispatch_deadline_s + self.lease_margin_s


class LogSettings(_Group):
    """Logging."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: Literal["json", "console"] = "json"


class Settings(BaseSettings):
    """Every setting, from the environment."""

    model_config = SettingsConfigDict(
        env_prefix="SCENEWISE_", env_nested_delimiter="__", frozen=True
    )

    media: MediaSettings = MediaSettings()
    inputs: InputSettings = InputSettings()
    service: ServiceSettings = Field(default_factory=ServiceSettings)
    log: LogSettings = LogSettings()
