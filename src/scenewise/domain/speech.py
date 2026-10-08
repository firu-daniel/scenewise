"""Speech values that cross the speech ports.

The policy functions (VAD runs, 30 s cuts, LID windows, the language rule, segment
merging) arrive with roadmap item 1 (q8c §2).
"""

from dataclasses import dataclass

from scenewise.domain.time import Seconds


@dataclass(frozen=True, slots=True, kw_only=True)
class SpeechProbabilities:
    """P(speech) for every hop of the whole track, from t = 0."""

    hop: Seconds
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class LanguageGuess:
    """One language-ID window's argmax guess (a BCP-47 primary subtag)."""

    language: str
    probability: float


@dataclass(frozen=True, slots=True, kw_only=True)
class LanguageReport:
    """What the language gate saw; ``detected`` includes "und" for unsure windows."""

    dominant: str | None
    detected: tuple[str, ...]
    partial: bool
