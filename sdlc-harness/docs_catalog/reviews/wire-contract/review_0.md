# Review 0 — docs/concepts/wire-contract.md (mode: catalog)

verdict: PASS

## Must Fix

None.

## Checks performed

1. **Anchors resolve.** Every path in `## Anchor files` and every inline path resolves from the repo root, and every named symbol greps inside its cited file. That covers constants, the four contract modules, `domain/jobs.py` `wire_status`, `decide_attempt` and `JobRecord`, `app/delivery.py` `handle_delivery`, `_attempt` and `_run`, `app/publish.py` `publish`, `service/http/push.py` `push`, `_rejected` and `_admitted`, `routes.py` `get_job`, `problems.py` `problem_response`, `cli.py` `analyse`, and the cited tests. The cited conventions sections also resolve: `conventions.md` "Shared state, storage paths and the wire contract", `app.md` "Not determined" and "The set that accompanies a new unit here".
2. **Line numbers.** Neither detector matched anything. The document has no line coordinates.
3. **Backend surface.** Checked against `push.py` and `routes.py`: `POST /v1/jobs` and `GET /v1/jobs/{job}` are spelled correctly, the 200 answers use `JSON_MEDIA_TYPE`, and problems are sent as `application/problem+json`.
4. **Data shapes.** Every field, default, `Literal` set and model config in the shape block matches `requests.py`, `results.py` and `records.py`. That includes `_Input` with `extra="forbid", frozen=True`, `_Output` with `frozen=True` only, `JobRecordV1` with `extra="forbid"`, the `ProblemV1` category set that includes `configuration`, and `RejectionV1.outcome`. The contract modules contain no `alias`.
5. **Mechanism.** The envelope claims match `envelope.py`: `None` only when there is no usable `job_id`, ASCII canonical JSON for the digest, and a lenient `_external_ref`. The `to_domain` error mapping and its single caller (`_run`) are correct. So are `record_from_json` raising `invariant_violation`, `status_json` going through `wire_status` (retry_wait), `result_json` with `indent=2` and the failed stage's `reason` / `ErrorInfoV1(retryable=False)`, and the CLI passing `FIRST_ATTEMPT` and `external_ref=()`.
6. **Depth.** The document traces consumers past the hints: delivery, publish, push, routes, problems, cli, and the `decide_attempt` conflict path. It also traces where `external_ref` comes from, which produces the null versus `{}` difference.
7. **Parity.** Skipped because `phases.parity` is false.
8. **Unverified markers.** The document has none, and none are needed.
9. **Omissions.** None material.
10. **Merge/supersede.** Not applicable because no `existing_doc` was passed.

## Notes (non-blocking)

- The `test_to_domain_rejects` citation in the first gotcha supports only the claim that `schema_version: "2"` gives `invalid_request`. The claim that this ends as a terminal `failed` record follows from `src/scenewise/app/delivery.py` (`_run`), which the gotcha could also cite. The claim is accurate either way.
