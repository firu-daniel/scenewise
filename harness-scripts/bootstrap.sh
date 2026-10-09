#!/usr/bin/env bash
# bootstrap.sh — provision a fresh scenewise checkout: what `commands.depInstall` runs. Hand-written
# for this repository, like publish-main.sh and release.sh: init does not generate it, and
# publish-main.sh removes harness-scripts/, so it never reaches main.
#
# WHY IT IS MORE THAN `uv sync`. setup-worktree.sh runs it in every working copy the harness cuts,
# on this machine and on a GitHub-hosted runner alike, and the hosted harness job provisions only
# Node, the claude CLI and the plugin. So it brings the toolchain itself:
#   1. uv, at exactly the version [tool.uv] required-version pins in pyproject.toml — installed
#      when absent (the standalone installer, into ~/.local/bin), refused when a different one is
#      on PATH, since every uv command would then refuse anyway;
#   2. ffmpeg, which the e2e tier needs — installed through apt when absent and apt is there with
#      passwordless sudo (a hosted runner), otherwise a refusal naming what to install;
#   3. the environment: `uv sync` with every CPU extra, the set ci.yml's static job installs, so
#      typecheck.sh and test.sh run against what CI runs against.
# Each step is skipped when already satisfied, so a re-run is cheap.
#
# Usage: bootstrap.sh
# Exit: 0 provisioned · 1 failed

set -uo pipefail

fail() {
  echo "bootstrap: $1" >&2
  exit 1
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$repo_root" ] || ! cd "$repo_root"; then
  fail "could not resolve a repository root from '${script_dir}' (is git on PATH?)"
fi

# --- 1. uv ---------------------------------------------------------------------------------------

# awk rather than a TOML parser: uv may not be here yet, and the system python3 can predate tomllib.
# [tool.ruff] has a required-version of its own, so the [tool.uv] table is matched first.
uv_version="$(awk '
  /^\[/ { in_uv = ($0 ~ /^\[tool\.uv\][[:space:]]*(#.*)?$/) }
  in_uv && /^required-version[[:space:]]*=/ { if (match($0, /"==[0-9]+\.[0-9]+\.[0-9]+"/)) print substr($0, RSTART + 3, RLENGTH - 4); exit }
' pyproject.toml)"
[ -n "$uv_version" ] || fail "could not read [tool.uv] required-version (==X.Y.Z) from pyproject.toml"

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "bootstrap: installing uv ${uv_version}"
  curl -LsSf "https://astral.sh/uv/${uv_version}/install.sh" \
    | env UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh \
    || fail "could not install uv ${uv_version}"
  # Later steps of a GitHub Actions job see it too.
  [ -z "${GITHUB_PATH:-}" ] || echo "$HOME/.local/bin" >>"$GITHUB_PATH"
fi
found="$(uv --version 2>/dev/null | awk '{ print $2 }')"
[ "$found" = "$uv_version" ] \
  || fail "uv ${found:-?} is on PATH, and pyproject.toml requires ${uv_version}: install that one ('uv self update ${uv_version}' when uv came from its installer)"

# --- 2. ffmpeg -----------------------------------------------------------------------------------

if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    echo "bootstrap: installing ffmpeg"
    sudo -n apt-get update -qq && sudo -n apt-get install -y -qq --no-install-recommends ffmpeg >/dev/null \
      || fail "could not install ffmpeg through apt"
  else
    fail "ffmpeg is not on PATH: install it (macOS: 'brew install ffmpeg'; Debian/Ubuntu: 'apt-get install ffmpeg')"
  fi
fi

# --- 3. The environment --------------------------------------------------------------------------

UV_LOCKED=1 uv sync --extra service --extra asr --extra llm-anthropic --extra vision --extra gcs --extra torch-cpu \
  || fail "uv sync failed"

echo "bootstrap: ready (uv ${uv_version}, $(ffmpeg -version 2>/dev/null | head -n 1 | awk '{ print $1, $3 }'))"
