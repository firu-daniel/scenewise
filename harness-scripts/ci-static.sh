#!/usr/bin/env bash
# ci-static.sh — the gate set harness-scripts/typecheck.sh runs: what commands.typecheck means for scenewise.
# Hand-written for this repository, like bootstrap.sh: init does not generate it, and
# publish-main.sh removes harness-scripts/, so it never reaches main. A separate script rather than
# a function inside typecheck.sh so that the wrapper's command line names a binary doctor can resolve.
# Run from the repository root (typecheck.sh changes into it first). Exit: the first failing gate's
# status, or 0.

set -uo pipefail

# With no arguments this mirrors the `static` job of .github/workflows/ci.yml, minus
# its `uv sync` (commands.depInstall, harness-scripts/bootstrap.sh, provisions the environment).
# Keep the two in step. With arguments, only mypy runs, over the paths given.
export UV_LOCKED=1 HF_HUB_DISABLE_TELEMETRY=1

# zizmor: the harness-*.yml workflows are audited at high severity only — the medium/low findings
# left in them (credential persistence in jobs that push, the unpinned claude CLI install) are
# kept on purpose upstream. Every other workflow takes the full audit.
audit_workflows() {
  local f product=() harness=()
  shopt -s nullglob
  for f in .github/workflows/*.yml .github/workflows/*.yaml; do
    case "${f##*/}" in
      harness-*) harness+=("$f") ;;
      *) product+=("$f") ;;
    esac
  done
  uv run zizmor --offline --no-config .github/dependabot.yml "${product[@]}" || return
  [ "${#harness[@]}" -eq 0 ] || uv run zizmor --offline --no-config --min-severity high "${harness[@]}"
}

static_gates() {
  if [ "$#" -gt 0 ]; then
    uv run mypy --config-file pyproject.toml "$@"
    return
  fi
  python3 scripts/check_stray_config.py &&
    uv lock --check &&
    bash scripts/check_lock.sh &&
    uv run ruff format --config pyproject.toml --check . &&
    uv run ruff check --config pyproject.toml . &&
    uv run mypy --config-file pyproject.toml &&
    uv run lint-imports --no-cache --config pyproject.toml &&
    uv run python scripts/check_module_size.py &&
    uv run python scripts/check_suppressions.py &&
    uv run deptry --config pyproject.toml src &&
    uv run vulture --config pyproject.toml &&
    uv run typos --isolated --config pyproject.toml &&
    audit_workflows
}

static_gates "$@"
