# Review: index (docs/INDEX.md)

mode: catalog · iteration: 1 · existing_doc: docs/INDEX.md (in-place revision) · verdict: PASS

## What changed since review_0 (uncommitted `git diff -- docs/INDEX.md`)

The only change is that the `### Link aliases` table under `## Gotchas / constraints` was removed. Nothing else in the INDEX moved.

## Checks

- **Removal of the alias table is correct (check 10, merge/supersede).** The table existed to map dangling `[[slug]]` aliases to real documents. The same working tree rewrites the `## Related` lines of audio-stage, cli-analyse, job-results-and-artifacts and job-submission so that they use the real slugs. A grep of every `[[slug]]` in `docs/features/*.md`, `docs/concepts/*.md` and `docs/INDEX.md` now returns only the 15 catalog slugs, and each one has a file. No alias is left that the table would need to explain. The `[[captions-stage]]` row's substance (no document, because captions is not wired) is now carried in audio-stage's Related line, and in the INDEX's own scope paragraph (the `StageName` docstring). No still-true content was dropped.
- **Coverage.** All 15 checklist entries (6 features, 9 concepts) are linked. Every Markdown link in the INDEX resolves on disk, and that includes the "Other documentation" targets.
- **Anchors (check 1).** `src/scenewise/domain/jobs.py` (`StageName`) resolves, and its docstring says the other stages "arrive with roadmap items 1-4". `src/scenewise/app/deps.py` (`enabled_stages`) resolves, and it adds non-audio stages only when their back ends are present. `ARCHITECTURE.md`, `README.md`, `docs/skeleton-notes.md`, `docs/decisions/initial-research.md`, `docs/research/open-decisions.md` and `docs/research/user-decisions.md` all exist.
- **Line numbers (check 2).** The colon detector returns no hits. The colon-less detector hits once, on `413/422/429/503`, which are HTTP status values and not coordinates. Kept.
- **`⚠️ unverified` roll-up (check 8).** It still matches the corpus. Only health-probes (the probe manifest, Q-5, Q-19) and configuration (the `REQUIRED_STAGES` env format, unknown-group env vars) carry markers.
- **Flagged for human review.** `sdlc-harness/docs_catalog/needs_review.md` does not exist, so the entry's fold-in instruction yields "None".
- **Parity (check 7).** Skipped because `phases.parity` is `false`. Its absence is not a finding.
- **Per-entry summaries.** The linked documents changed only in their Related lines, plus the `to_domain` anchor fix in job-results-and-artifacts. None of the INDEX one-liners depends on those lines, so the review_0 verification of the summaries still holds.

## Must Fix

None.

## Advisory (does not affect the verdict)

- The "Flagged for human review" sentence says "Every document in this catalog passed `docs-reviewer` within the fix cap". At the time of this review, the latest review file for job-results-and-artifacts is `links_review_0.md`, and its verdict is **FAIL**. That FAIL is for `to_domain`, which was anchored to the wrong file. The working tree already applies the correction: `to_domain` is now anchored to `src/scenewise/app/contract/mapping.py`, where `def to_domain` is defined, and it is added to that Anchor-files entry. But it has not been re-reviewed yet. If that re-review does not pass within the cap, this sentence becomes false, and job-results-and-artifacts must be listed under Flagged for human review.
