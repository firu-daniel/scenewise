# Review 0: docs/concepts/configuration.md (mode: catalog)

verdict: PASS

## Scope checked
- Every field, default, type and env-variable spelling in the "How it works" table against `src/scenewise/service/config.py` (`MediaSettings`, `InputSettings`, `ServiceSettings`, `LogSettings`, `_Group`, `Settings`, `_default_state_prefix`). All match.
- `_timing` invariant, error message, `lease_s` = 1920 against `ServiceSettings._timing` / `lease_s` and `tests/unit/test_service.py` (`test_timing_invariant`). Correct.
- Every consumer named in the "Read by" column: `src/scenewise/service/bootstrap.py` (`build_dependencies`, `_stores`), `src/scenewise/service/http/app.py` (`create_app`), `src/scenewise/service/http/push.py` (`push`, `_admitted`, `read_body`), `src/scenewise/service/http/routes.py` (`get_job`), `src/scenewise/service/cli.py` (`main`, `analyse`, `_with_local_root`), `src/scenewise/service/logs.py` (`configure`). No other `Settings` consumer exists under `src`.
- Start-up failure paths: `find_binaries` codes `ffmpeg_unavailable` / `ffmpeg_too_old`, `stage_unavailable`, `store_unavailable`, CLI exit 2 and stderr formats, no handler in the lifespan, `http_status` fallback to 500. Correct.
- Store roots / exclusion (`src/scenewise/adapters/storage/local.py` (`LocalBlobStore._path`)), `artifacts_prefix` rejection (`src/scenewise/app/delivery.py`). Correct.
- Cited documents: `ARCHITECTURE.md` §10 group list, `docs/skeleton-notes.md` A7, `.claude/context/service.md` "Settings" and "Not determined", `.claude/context/conventions.md` "Constants and configuration", `README.md` "Run the audio stage", `.env.example` quote. All resolve and say what the doc attributes to them.
- Module constants `RETRY_AFTER_BUSY_S` (push.py), `RETRY_AFTER_STORAGE_S` (routes.py), `PROBE_TIMEOUT_S` (ffmpeg.py) exist.
- All anchor paths and symbols resolve from the repo root; every `[[slug]]` cross-link has a file under `docs/`.
- Line-number detectors: both regexes return zero hits; no coordinates.
- Parity check skipped (`phases.parity` is false). No `existing_doc`, so no merge check.

## Findings (advisory, not verdict-changing)

1. `⚠️ unverified` on `SCENEWISE_SERVICE__REQUIRED_STAGES` (How it works table, `required_stages` row) is not genuinely unverifiable. A one-line run in the project venv confirms it: `SCENEWISE_SERVICE__REQUIRED_STAGES='["captions"]'` yields `frozenset({StageName.CAPTIONS})`, and `'["audio"]'` yields `{StageName.AUDIO}`. The claim is correct.
   Correction: drop the marker and state that the variable is a JSON array of stage wire names (`StageName` values in `src/scenewise/domain/jobs.py` (`StageName`)), for example `'["audio"]'`.

2. `⚠️ unverified` on unknown-group variables (Gotchas, first bullet) is likewise checkable. With `SCENEWISE_ASR__BACKEND=x` set, `Settings()` builds without error and the variable has no effect. pydantic-settings reads only env variables that map to declared fields, so `_Group`'s `extra="forbid"` is never triggered by environment input. The claim is correct.
   Correction: drop the marker and keep the sentence "nothing reads it, and it does not cause a validation error".
