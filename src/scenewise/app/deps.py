"""The long-lived port implementations a job runs with; nothing per job is stored."""

from dataclasses import dataclass

from scenewise.domain.jobs import StageName
from scenewise.ports import (
    BlobStore,
    ImageModerator,
    ImageReader,
    LanguageIdentifier,
    MediaTool,
    Notifier,
    SpeechRecognizer,
    TextGenerator,
    VoiceActivityDetector,
    ZeroShotLabeller,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Speech:
    """The captions stage needs all three."""

    vad: VoiceActivityDetector
    lid: LanguageIdentifier
    recognizer: SpeechRecognizer


@dataclass(frozen=True, slots=True, kw_only=True)
class Dependencies:
    """Port bundle built once by ``service.bootstrap``; ``None`` = not offered."""

    store: BlobStore  # job records and artifacts
    inputs: BlobStore  # request inputs only; never sees the state or artifact roots
    media: MediaTool
    images: ImageReader
    speech: Speech | None = None
    text: TextGenerator | None = None
    moderator: ImageModerator | None = None
    labeller: ZeroShotLabeller | None = None
    notifier: Notifier | None = None  # None until HTTP callbacks are built
    enabled_stages: frozenset[StageName]


def enabled_stages(
    *,
    speech: Speech | None,
    text: TextGenerator | None,
    moderator: ImageModerator | None,
    labeller: ZeroShotLabeller | None,
) -> frozenset[StageName]:
    """The stages a deployment with these back ends can run."""
    stages = {StageName.AUDIO}  # needs only the media tool, which is always present
    if speech is not None:
        stages.add(StageName.CAPTIONS)
        if text is not None:
            stages |= {StageName.SUMMARY, StageName.CHAPTERS}
    if labeller is not None:
        stages.add(StageName.LABELS)
        if moderator is not None:
            stages.add(StageName.MODERATION)
    return frozenset(stages)
