"""Which stages run for a request, in which order, and what each needs."""

from collections.abc import Iterable, Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from scenewise.domain.jobs import StageName


class Needs(StrEnum):
    """The input a stage cannot run without."""

    AUDIO = "audio"
    TRANSCRIPT = "transcript"  # v1: summary and chapters are speech-only (U14)
    VISUAL = "visual"


PREREQUISITES: Final[Mapping[StageName, Needs]] = MappingProxyType(
    {
        StageName.AUDIO: Needs.AUDIO,
        StageName.CAPTIONS: Needs.AUDIO,
        StageName.SUMMARY: Needs.TRANSCRIPT,
        StageName.CHAPTERS: Needs.TRANSCRIPT,
        StageName.MODERATION: Needs.VISUAL,
        StageName.LABELS: Needs.VISUAL,
    }
)

_ORDER: Final = tuple(StageName)


def ordered(stages: Iterable[StageName]) -> tuple[StageName, ...]:
    """The requested stages in run order: producers before their consumers."""
    wanted = frozenset(stages)
    return tuple(stage for stage in _ORDER if stage in wanted)


def unavailable(
    requested: Iterable[StageName], enabled: frozenset[StageName]
) -> tuple[StageName, ...]:
    """The requested stages this deployment does not offer, in run order."""
    return tuple(stage for stage in ordered(requested) if stage not in enabled)
