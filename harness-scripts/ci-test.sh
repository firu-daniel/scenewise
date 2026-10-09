#!/usr/bin/env bash
# ci-test.sh — the gate set harness-scripts/test.sh runs: what commands.test means for scenewise.
# Hand-written for this repository, like bootstrap.sh: init does not generate it, and
# publish-main.sh removes harness-scripts/, so it never reaches main. A separate script rather than
# a function inside test.sh so that the wrapper's command line names a binary doctor can resolve.
# Run from the repository root (test.sh changes into it first). Exit: the first failing gate's
# status, or 0.

set -uo pipefail

# With no arguments this mirrors one Python of the `test` job of
# .github/workflows/ci.yml — the model-marker check, the unit tier at 100% core coverage, every PR
# tier at 90% overall, and the no-skip check — on the interpreter the environment carries. Keep
# the two in step. With arguments, pytest runs alone over them, with no coverage gate.
export UV_LOCKED=1 HF_HUB_DISABLE_TELEMETRY=1
CORE="src/scenewise/domain/*,src/scenewise/app/*,src/scenewise/ports.py,src/scenewise/ports/*"

model_marker_check() {
  local out code bad
  out="$(uv run pytest -c pyproject.toml -m model --collect-only -q)"
  code=$?
  if [ "$code" -ne 0 ] && [ "$code" -ne 5 ]; then
    echo "$out"
    echo "test: collection failed ($code)" >&2
    return 1
  fi
  bad="$(grep '::' <<<"$out" | grep -v '^tests/contract/' || true)"
  if [ -n "$bad" ]; then
    echo "test: model-marked tests outside tests/contract:" >&2
    echo "$bad" >&2
    return 1
  fi
}

test_gates() {
  if [ "$#" -gt 0 ]; then
    uv run pytest -c pyproject.toml "$@"
    return
  fi
  model_marker_check &&
    COVERAGE_FILE=.coverage.unit uv run pytest -c pyproject.toml tests/unit --cov --cov-config=pyproject.toml \
      --cov-report= --cov-fail-under=0 --junitxml=pytest-unit.xml &&
    uv run coverage report --rcfile=pyproject.toml --data-file=.coverage.unit --include="$CORE" --fail-under=100 &&
    uv run pytest -c pyproject.toml --cov --cov-config=pyproject.toml --cov-report=xml --junitxml=pytest.xml &&
    uv run python scripts/check_junit.py pytest-unit.xml pytest.xml
}

test_gates "$@"
