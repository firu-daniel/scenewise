# Review 0: docs/concepts/layering-and-ports.md

verdict: FAIL

The document is accurate and well researched. It traces the bundle from `build_dependencies` through both builders (`create_app` lifespan, `analyse`) to every consumer (`run_job`, `handle_delivery`/`_run`, `get_job`, `readyz`, `fake_dependencies`). The import-linter contracts, the ten ports, the `Dependencies` fields, the `enabled_stages` rules, `_stores` and the `ARCHITECTURE.md` §4 departures (A6, A8, A10) all match the source. Both line-number detectors return no hits. Two factual errors and one path-form problem remain.

## Must Fix

1. **Frames are presented as an existing `app` function. They are not.**
   - Claim (How it works › Ports, last bullet): "Frames, audio acquisition and publishing are **not** ports. They are plain `app` functions over `MediaTool`, `ImageReader` and `BlobStore` (`ARCHITECTURE.md` §4)."
   - Contradicted by: `src/scenewise/app/` has no `frames.py`. The modules there are `audio.py`, `constants.py`, `deps.py`, `delivery.py`, `publish.py`, `runner.py`, `stages.py` and `contract/`. `docs/skeleton-notes.md` A10 lists `app/{frames,…}` under "Absent". The document's own Gotchas also say "No `app` module reads `deps.images`", so no `app` function runs over `ImageReader` today.
   - Correction: say that audio acquisition (`src/scenewise/app/audio.py` (`acquire_audio`)) and publishing (`src/scenewise/app/publish.py` (`publish`)) are plain `app` functions over `MediaTool` and `BlobStore`. Say that frames are planned the same way (`app/frames.py` in `ARCHITECTURE.md` §4) but are absent from the skeleton (`docs/skeleton-notes.md` A10).

2. **"Nothing imports it" (the `service` row of the layer table) is false as written.**
   - Contradicted by: `src/scenewise/__main__.py` runs `from scenewise.service.cli import main`, which the document's own next paragraph describes.
   - Correction: "No other layer imports it; only the layers-exempt `__main__` does."

3. **Some paths do not resolve from the repo root.** Every path in a document must be repo-relative, in prose as much as in an anchor.
   - Line with the `tests/contract` mixins (Gotchas, "A port in use comes with…"): `mediatool_contract.py` (`MediaToolContract`) and `imagereader_contract.py` (`ImageReaderContract`) are anchors whose path half resolves only from inside `tests/contract/`. Correction: `tests/contract/mediatool_contract.py` (`MediaToolContract`), `tests/contract/imagereader_contract.py` (`ImageReaderContract`).
   - Layer table, `app` row: `app/contract/` and `app/deps.py`. Correction: `src/scenewise/app/contract/` and `src/scenewise/app/deps.py`.
   - Layer table, `package` row: `__init__.py` and `__main__.py`. Correction: `src/scenewise/__init__.py` and `src/scenewise/__main__.py`.
   - Gotchas, "order of work" and "lazily too": `ports.py` and `bootstrap.py`. Correction: `src/scenewise/ports.py` and `src/scenewise/service/bootstrap.py`.
   - Gotchas, "Naming": `adapters/<kind>/<technology>.py`. Correction: `src/scenewise/adapters/<kind>/<technology>.py`.
   - Layer table, `adapters` row: `media/` and `storage/` are subpackage names given as a listing. They may stay if worded as names, or become `src/scenewise/adapters/media/` and `src/scenewise/adapters/storage/`.

## Verified (no action)
- `pyproject.toml` `[tool.importlinter]`: all six contracts, their types and their settings (`exhaustive`, `exhaustive_ignores = ["__main__"]`, `allowed_importers`, `allow_indirect_imports = true`, the `allowed` list), plus the bootstrap `PLC0415` ignore "the only lazy imports in src".
- `scripts/import_contracts.py` (`AllowedExternalsContract`): stdlib, root packages and `allowed` (plus `__future__`).
- `src/scenewise/ports.py`: ten Protocols, `Blob`, `WriteConflictError`, `ABSENT_GENERATION`, `AUDIO_SAMPLE_RATE`, `AUDIO_CHANNELS`, the "Ports are synchronous" docstring, and domain/stdlib-only imports.
- `src/scenewise/app/deps.py`: the `Dependencies` field block, `Speech`, and the `enabled_stages` rules.
- `src/scenewise/service/bootstrap.py`: the order inside `build_dependencies`, the `_stores` match, `store_unavailable` and `stage_unavailable`, and the module docstring's extension plan.
- `src/scenewise/adapters/media/ffmpeg.py` (`find_binaries`): `ffmpeg_unavailable` and `ffmpeg_too_old`.
- `src/scenewise/adapters/storage/local.py` (`LocalBlobStore.__init__`): `roots` and `excluded`.
- No adapter subclasses a Protocol. Adapters import only `domain` and `ports`.
- Builders and consumers: `create_app`, `ServiceState.deps`, `analyse`, `_with_local_root`, `run_job`, `handle_delivery`, `_Delivery`, `_run`, `job_status(store=…)`, `get_job`, `readyz`, push to `handle_delivery`, and `fake_dependencies` (inputs defaults to store).
- `tests/e2e/test_bootstrap.py` test names, the contract mixin class names, `ARCHITECTURE.md` §4 (required `notifier`, `guard`, no `inputs`) and §14, and `.claude/context` "Order of work", `## Not determined` and adapter naming.
