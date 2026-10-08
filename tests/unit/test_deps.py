from typing import TYPE_CHECKING, cast

from scenewise.app.deps import Speech, enabled_stages
from scenewise.domain.jobs import StageName

if TYPE_CHECKING:
    from scenewise.ports import (
        ImageModerator,
        LanguageIdentifier,
        SpeechRecognizer,
        TextGenerator,
        VoiceActivityDetector,
        ZeroShotLabeller,
    )

SPEECH = Speech(
    vad=cast("VoiceActivityDetector", object()),
    lid=cast("LanguageIdentifier", object()),
    recognizer=cast("SpeechRecognizer", object()),
)
TEXT = cast("TextGenerator", object())
MODERATOR = cast("ImageModerator", object())
LABELLER = cast("ZeroShotLabeller", object())


def test_skeleton_offers_audio_only() -> None:
    stages = enabled_stages(speech=None, text=None, moderator=None, labeller=None)
    assert stages == {StageName.AUDIO}


def test_text_needs_speech_and_moderation_needs_the_labeller() -> None:
    assert enabled_stages(
        speech=None, text=TEXT, moderator=MODERATOR, labeller=None
    ) == {StageName.AUDIO}


def test_every_back_end_enables_every_stage() -> None:
    stages = enabled_stages(
        speech=SPEECH, text=TEXT, moderator=MODERATOR, labeller=LABELLER
    )
    assert stages == set(StageName)


def test_partial_back_ends() -> None:
    stages = enabled_stages(speech=SPEECH, text=None, moderator=None, labeller=LABELLER)
    assert stages == {StageName.AUDIO, StageName.CAPTIONS, StageName.LABELS}
