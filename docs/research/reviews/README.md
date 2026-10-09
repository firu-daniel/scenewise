# Review files (deleted)

The review rounds of the research and of the skeleton (`q*-review-r*.md`, `deliverable-*-review-r*.md`,
`skeleton-review-r1.md`) were deleted on 2026-10-09, once the research was done and every finding had been applied
or recorded. The research documents and `docs/skeleton-notes.md` still cite them by file name.

They remain in the history. To list them, and to read one:

```sh
git log --diff-filter=D --name-only --format='%h %s' -- docs/research/reviews
git show <that commit>^:docs/research/reviews/<file>
```
