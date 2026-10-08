import json

from scenewise.app.publish import attempt_prefix, publish
from scenewise.domain.jobs import SkipReason, StageName, job_id
from scenewise.domain.results import Analysis, Skipped, StageOutcome, Succeeded
from tests.fakes import CLIP, InMemoryBlobStore, wav_bytes


def test_attempt_prefix() -> None:
    assert attempt_prefix("mem://out/", 3) == "mem://out/a3"


def test_publish_writes_the_track_and_the_result() -> None:
    store = InMemoryBlobStore()
    wav = wav_bytes(0.5)
    analysis = Analysis(
        job_id=job_id("j"),
        media=CLIP,
        outcomes=(StageOutcome(stage=StageName.AUDIO, outcome=Succeeded(), seconds=1),),
        audio_wav=wav,
    )
    uri = publish(analysis, store=store, prefix="mem://out", attempt=2, external_ref=())
    assert uri == "mem://out/a2/result.json"
    assert store.objects["mem://out/a2/audio.wav"].data == wav
    assert store.objects["mem://out/a2/audio.wav"].content_type == "audio/wav"
    result = json.loads(store.objects[uri].data)
    assert result["stages"]["audio"]["uri"] == "mem://out/a2/audio.wav"
    assert result["attempt"] == 2


def test_publish_without_a_track() -> None:
    store = InMemoryBlobStore()
    skipped = Skipped(reason=SkipReason.NO_AUDIO_STREAM)
    analysis = Analysis(
        job_id=job_id("j"),
        media=None,
        outcomes=(StageOutcome(stage=StageName.AUDIO, outcome=skipped, seconds=0),),
    )
    uri = publish(analysis, store=store, prefix="mem://out", attempt=1, external_ref=())
    assert set(store.objects) == {uri}
