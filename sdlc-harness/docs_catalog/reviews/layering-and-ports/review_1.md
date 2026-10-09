# Review 1: docs/concepts/layering-and-ports.md

verdict: FAIL

Checked: every anchor in `## Anchor files` and every inline path/symbol (all resolve); both line-number detectors (zero hits for either); the six import-linter contracts and the ruff `PLC0415` exemption in `pyproject.toml`; `AllowedExternalsContract`; the ten ports, `Blob`, `WriteConflictError` and the three constants in `src/scenewise/ports.py`; the `Dependencies` / `Speech` / `enabled_stages` logic; `build_dependencies` / `_stores` step by step; the builders (`create_app`, `analyse`, `_with_local_root`); the consumers (`run_job`, `handle_delivery`, `_Delivery`, `_run`, `job_status`, `readyz`, `get_job`); `fake_dependencies`; the contract mixins; the e2e bootstrap tests; `ARCHITECTURE.md` §4 and §14; `docs/skeleton-notes.md` A6, A8 and A10; and the cited `## Not determined` entries in `.claude/context/conventions.md` and `.claude/context/service.md`. Except for the item below, these all match the code. The research goes past the hints: it covers the builders, the consumers, the test fakes, the contract mixins and the departures from the architecture.

## Must Fix

1. **The `routes.py` consumer bullet gives one function's work to another, and contradicts the "No consumer reads `Settings`" lead-in** (`## How it works` -> `### Who builds and who consumes the bundle` -> Consumers, the `src/scenewise/service/http/routes.py` (`readyz`) bullet).
   - Claim: `routes.py` (`readyz`) "reports `deps.enabled_stages`, and passes `state.deps.store` to the status use case". The bullets sit under the heading "No consumer reads `Settings`".
   - Contradicting source: `src/scenewise/service/http/routes.py`. `readyz` only reports `_state(request).deps.enabled_stages`. The function that passes `store=state.deps.store` to `job_status` is `get_job`. `get_job` also passes `state_prefix=state.settings.service.state_prefix`, so this consumer does read `Settings`.
   - Correction: split the bullet into `readyz` (reports `deps.enabled_stages`) and `get_job` (passes `state.deps.store` and `state.settings.service.state_prefix` to `job_status`). Narrow the lead-in to what is true: the `app` use cases (`run_job`, `handle_delivery`, `job_status`) never read `Settings`, and the `service` routes do. Add `get_job` to the `routes.py` anchor. Today `routes.py` is not in `## Anchor files` at all, so add it.

## Should Fix (non-blocking)

- **The HTTP route that hands the bundle to delivery is missing from the consumer list.** `src/scenewise/service/http/push.py` (`push` / `_admitted`) passes `deps=state.deps` to `handle_delivery`. That is the production path into `handle_delivery`, but only `[[job-submission]]` mentions it. Add one bullet and an anchor entry for `src/scenewise/service/http/push.py`.
- **The field block has a comment that is not in the code.** `speech: Speech | None = None        # None = this deployment does not offer the stage` is not a line in `src/scenewise/app/deps.py`. There, `None = not offered` is in the `Dependencies` class docstring, and the per-field wording comes from `ARCHITECTURE.md` §4. Either drop the comment, or say the meaning comes from the class docstring, so the block reads as the source.
- **Two contract names are shortened.** The real names end in "(q8a §1.5 rule 6, as an allow-list)". The quoted prefixes still grep, so this is cosmetic.

missed_docs: n/a (catalog mode)
