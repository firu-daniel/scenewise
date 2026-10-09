"""The ``scenewise`` command line.

``scenewise analyse FILE --out DIR`` runs the requested stages on a local file and
prints the result document; it writes artifacts to ``DIR`` and keeps no job record.
``run-job --job-uri`` (the Cloud Run job path) and ``calibrate`` (item 4) come later.
"""

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from scenewise import __version__
from scenewise.app.contract import mapping
from scenewise.app.publish import AUDIO_FILE_NAME
from scenewise.app.runner import run_job
from scenewise.domain.errors import ConfigurationError, ScenewiseError
from scenewise.domain.inputs import AudioFile
from scenewise.domain.jobs import FIRST_ATTEMPT, Job, JobSpec, StageName, job_id
from scenewise.service import logs
from scenewise.service.bootstrap import build_dependencies
from scenewise.service.config import Settings

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
EXIT_CONFIGURATION: Final = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scenewise")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    analyse = commands.add_parser("analyse", help="analyse one local media file")
    analyse.add_argument("file", type=Path)
    analyse.add_argument("--out", type=Path, required=True, help="artifact directory")
    analyse.add_argument(
        "--stage",
        dest="stages",
        action="append",
        type=StageName,
        choices=list(StageName),
        help="stage to run (repeatable; default: audio)",
    )
    return parser


def _with_local_root(settings: Settings, root: Path) -> Settings:
    roots = (*settings.inputs.local_roots, root)
    inputs = settings.inputs.model_copy(update={"local_roots": roots})
    return settings.model_copy(update={"inputs": inputs})


def analyse(
    media: Path, *, out: Path, stages: Sequence[StageName], settings: Settings
) -> int:
    """Run ``stages`` on ``media``, write artifacts to ``out``, print the result."""
    media = media.resolve()
    settings = _with_local_root(settings, media.parent)
    try:
        deps = build_dependencies(settings)
        job = Job(
            id=job_id("cli"),
            spec=JobSpec(stages=frozenset(stages)),
            audio=AudioFile(uri=media.as_uri()),
        )
        deadline = time.monotonic() + settings.service.attempt_budget_s
        analysis = run_job(job, deps, deadline=deadline)
    except ScenewiseError as e:
        sys.stderr.write(f"scenewise: {e.code}: {e.detail}\n")
        return EXIT_CONFIGURATION if isinstance(e, ConfigurationError) else EXIT_FAILED
    audio_uri = None
    if analysis.audio_wav is not None:
        out.mkdir(parents=True, exist_ok=True)
        target = out / AUDIO_FILE_NAME
        target.write_bytes(analysis.audio_wav)
        audio_uri = target.resolve().as_uri()
    document = mapping.result_json(
        analysis, attempt=FIRST_ATTEMPT, external_ref=(), audio_uri=audio_uri
    )
    sys.stdout.write(document.decode() + "\n")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv`` and run the command; returns the process exit code."""
    args = _parser().parse_args(argv)
    try:
        settings = Settings()
    except ValidationError as e:
        fields = ", ".join(".".join(map(str, err["loc"])) for err in e.errors())
        sys.stderr.write(f"scenewise: invalid settings: {fields}\n")
        return EXIT_CONFIGURATION
    logs.configure(settings.log)
    stages: list[StageName] = args.stages or [StageName.AUDIO]
    return analyse(args.file, out=args.out, stages=stages, settings=settings)
