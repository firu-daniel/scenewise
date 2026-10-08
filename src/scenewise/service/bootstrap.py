"""COMPOSITION ROOT: Settings -> system checks -> adapters -> ``Dependencies``.

The only module that imports ``scenewise.adapters``. Back ends behind an optional
extra are imported lazily inside the ``match`` branch that selects them, so a missing
extra is a ``ConfigurationError``, not an ``ImportError``. The model back ends (asr,
llm, vision) and the GCS store join here with their roadmap items.
"""

from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

from scenewise.app.deps import Dependencies, enabled_stages
from scenewise.domain.errors import ConfigurationError
from scenewise.ports import BlobStore
from scenewise.service.config import Settings


def _stores(settings: Settings) -> tuple[BlobStore, BlobStore]:
    """The output store (records, artifacts) and the separate input store."""
    state = urlsplit(settings.service.state_prefix)
    match state.scheme:
        case "file":
            from scenewise.adapters.storage.local import LocalBlobStore

            outputs = [Path(url2pathname(state.path)), *settings.service.artifact_roots]
            return (
                LocalBlobStore(roots=outputs),
                LocalBlobStore(roots=settings.inputs.local_roots, excluded=outputs),
            )
        case scheme:
            detail = f"no store for {scheme}:// state_prefix yet; use file://"
            raise ConfigurationError(code="store_unavailable", detail=detail)


def build_dependencies(settings: Settings) -> Dependencies:
    """Check the system, build every adapter once, and check required stages."""
    from scenewise.adapters.media.ffmpeg import FfmpegMediaTool, find_binaries
    from scenewise.adapters.media.images import PillowImageReader

    ffmpeg, ffprobe = find_binaries(
        ffmpeg=settings.media.ffmpeg,
        ffprobe=settings.media.ffprobe,
        min_major=settings.media.min_major,
    )
    stages = enabled_stages(speech=None, text=None, moderator=None, labeller=None)
    if missing := settings.service.required_stages - stages:
        names = ", ".join(sorted(missing))
        detail = f"required stages have no back end: {names}"
        raise ConfigurationError(code="stage_unavailable", detail=detail)
    store, inputs = _stores(settings)
    return Dependencies(
        store=store,
        inputs=inputs,
        media=FfmpegMediaTool(ffmpeg=ffmpeg, ffprobe=ffprobe),
        images=PillowImageReader(),
        enabled_stages=stages,
    )
