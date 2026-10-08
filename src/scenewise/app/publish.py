"""``publish()``: write one attempt's artifacts; never touches the job record."""

from scenewise.app.contract import mapping
from scenewise.domain.results import Analysis
from scenewise.ports import BlobStore


def attempt_prefix(prefix: str, attempt: int) -> str:
    """The attempt-scoped artifact prefix ``{prefix}/a{attempt}``."""
    return f"{prefix.rstrip('/')}/a{attempt}"


def publish(
    analysis: Analysis,
    *,
    store: BlobStore,
    prefix: str,
    attempt: int,
    external_ref: tuple[tuple[str, str], ...],
) -> str:
    """Write ``audio.wav`` (if produced) and ``result.json``; return the result URI."""
    base = attempt_prefix(prefix, attempt)
    audio_uri = None
    if analysis.audio_wav is not None:
        audio_uri = f"{base}/audio.wav"
        store.write(audio_uri, analysis.audio_wav, content_type="audio/wav")
    result_uri = f"{base}/result.json"
    document = mapping.result_json(
        analysis, attempt=attempt, external_ref=external_ref, audio_uri=audio_uri
    )
    store.write(result_uri, document, content_type="application/json")
    return result_uri
