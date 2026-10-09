#!/usr/bin/env bash
# release.sh — run a whole scenewise release from one terminal: bump the version on dev, publish dev
# onto main, tag the publication `v<version>` and create its GitHub Release. Hand-written for this
# repository, after the autonomous-sdlc-harness repository's release.sh and tag-release.sh: init
# does not generate it, and publish-main.sh removes harness-scripts/, so it never reaches main.
# scenewise is not published to a package index; the tag and the GitHub Release are the release.
#
# THE STEPS, each one skipped when it is already done — so a run that stopped part-way (a failed
# check, a Ctrl-C) is resumed by running the same command again:
#
#   1. Bump. A branch `chore_bump_version_<x_y_z>` cut from origin/dev in a throwaway worktree (the
#      caller's checkout is never touched), `uv version <version>` (pyproject.toml and the project's
#      own uv.lock entry, nothing else), a pull request onto dev, its required checks waited for,
#      then squash-merged. Skipped when origin/dev already carries the version; an open pull
#      request from that branch is reused rather than recreated.
#   2. Publish onto main. The push to dev runs .github/workflows/publish-main.yml, which stages the
#      publication on `publish`; this waits for that run, opens the `publish` → main pull request
#      (Actions may not open it here — see publish-main.sh), waits for its checks and merges it with
#      Rebase and merge, the only method main's ruleset allows. Skipped when origin/main already
#      carries the version.
#   3. Tag. An annotated `v<version>` on the OLDEST commit of origin/main's first-parent line whose
#      pyproject.toml carries the version — the bump's publication; a later commit with the same
#      version holds work published after the release. An existing tag elsewhere is never moved.
#   4. GitHub Release for the tag, with generated notes. Skipped when it exists.
#
# WHO RUNS IT. The operator, at a terminal, with `gh` logged in as the repository admin. Both merges
# use `gh pr merge --admin`: dev-protection requires an approval the pull request's own author
# cannot give, and main-protection restricts updates to the admin role — both rulesets let that role
# bypass through a pull request only, which is the route taken here. Nothing pushes to a protected
# branch, which githooks/pre-push would refuse anyway. Without --dry-run it refuses unless stdin is
# a terminal: a release is made by a person, and an unattended run's Bash tool has none.
#
# Usage: release.sh <version> [--dry-run] [--yes]
#   --dry-run  report which steps are done and which would run; change nothing
#   --yes      skip the one confirmation before the first change
# Exit: 0 released, or already released · 1 refused or failed · 2 bad usage

set -uo pipefail

usage() {
  echo "release: $1" >&2
  echo "  usage: release.sh <version> [--dry-run] [--yes]" >&2
  exit 2
}

fail() {
  echo "release: $1" >&2
  exit 1
}

say() {
  echo "release: $1"
}

version=""
dry_run=0
assume_yes=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    --yes) assume_yes=1 ;;
    -*) usage "unrecognized argument '$arg'" ;;
    *)
      [ -z "$version" ] || usage "unexpected second version '$arg'"
      version="$arg"
      ;;
  esac
done
[ -n "$version" ] || usage "missing <version>"

# PEP 440 release versions only, the subset uv and a `v<x>` tag agree on.
version_re='^[0-9]+\.[0-9]+\.[0-9]+((a|b|rc)[0-9]+)?$'
[[ "$version" =~ $version_re ]] \
  || usage "'$version' is not a MAJOR.MINOR.PATCH version (an optional aN, bN or rcN suffix is allowed)"

for tool in gh uv; do
  command -v "$tool" >/dev/null 2>&1 || fail "$tool is required and is not on PATH"
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$repo_root" ] || ! cd "$repo_root"; then
  fail "could not resolve a repository root from '${script_dir}' (is git on PATH?)"
fi

tag="v${version}"
bump_branch="chore_bump_version_${version//./_}"
title="chore: bump version to ${version}"
poll_seconds=10

slug="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)" \
  || fail "gh could not resolve this repository (is it logged in? try 'gh auth status')"

# The [project] version a ref's pyproject.toml carries, or nothing.
version_at() {
  git cat-file blob "$1:pyproject.toml" 2>/dev/null \
    | uv run --no-project --quiet python -c 'import sys, tomllib; print(tomllib.load(sys.stdin.buffer)["project"]["version"])' 2>/dev/null
}

fetch() {
  git fetch --quiet --tags origin main dev || fail "could not fetch main, dev and tags from origin"
}

# Wait for the first run of <workflow> that matches the jq filter <select>, then watch it to the
# end. No deadline: a queued runner is slow, not failed, and Ctrl-C is always there.
watch_run() {
  local workflow="$1" select="$2" what="$3" run_id=""
  say "waiting for the ${what} run of ${workflow}…"
  while [ -z "$run_id" ]; do
    run_id="$(gh run list --repo "$slug" --workflow "$workflow" --limit 20 \
      --json databaseId,headSha --jq "[.[] | select(${select})][0].databaseId // empty" 2>/dev/null)"
    [ -n "$run_id" ] || sleep "$poll_seconds"
  done
  gh run watch "$run_id" --repo "$slug" --exit-status --interval "$poll_seconds" >/dev/null \
    || fail "${workflow} run ${run_id} failed: gh run view ${run_id} --repo ${slug} --log-failed"
  say "${workflow} run ${run_id} passed"
}

# Wait for a pull request's checks to finish and pass. A just-pushed head can have no checks
# reported yet, which `gh pr checks` treats as an error, so that state is waited out first.
watch_checks() {
  local pr="$1"
  say "waiting for the checks on #${pr}…"
  until [ "$(gh pr view "$pr" --repo "$slug" --json statusCheckRollup --jq '.statusCheckRollup | length' 2>/dev/null)" -gt 0 ] 2>/dev/null; do
    sleep "$poll_seconds"
  done
  gh pr checks "$pr" --repo "$slug" --watch --fail-fast --interval "$poll_seconds" >/dev/null \
    || fail "checks failed on #${pr}: gh pr checks ${pr} --repo ${slug}"
  say "checks passed on #${pr}"
}

open_pr() {
  gh pr list --repo "$slug" --head "$1" --base "$2" --state open --json number --jq '.[0].number // empty'
}

fetch
dev_version="$(version_at refs/remotes/origin/dev)"
main_version="$(version_at refs/remotes/origin/main)"
[ -n "$dev_version" ] || fail "could not read the version origin/dev carries"

bump_done=0
publish_done=0
release_done=0
[ "$dev_version" = "$version" ] && bump_done=1
[ "$main_version" = "$version" ] && publish_done=1
gh release view "$tag" --repo "$slug" >/dev/null 2>&1 && release_done=1

if [ "$bump_done" -eq 0 ]; then
  newest="$(printf '%s\n' "$dev_version" "$version" | sort -V | tail -n 1)"
  [ "$newest" = "$version" ] || fail "origin/dev is already at ${dev_version}, past ${version}"
fi

state() { [ "$1" -eq 1 ] && echo "done" || echo "to do"; }
say "releasing ${version} (dev ${dev_version}, main ${main_version:-none})"
echo "  1. bump on dev        $(state "$bump_done")"
echo "  2. publish onto main  $(state "$publish_done")"
echo "  3. tag ${tag}"
echo "  4. GitHub Release     $(state "$release_done")"

[ "$dry_run" -eq 0 ] || exit 0
[ "$release_done" -eq 0 ] || { say "${tag} is already released"; exit 0; }
[ -t 0 ] || fail "stdin is not a terminal; a release is run by a person at a terminal (use --dry-run to inspect)"

if [ "$assume_yes" -eq 0 ]; then
  read -r -p "release: proceed? [y/N] " answer
  [[ "$answer" =~ ^[Yy]$ ]] || fail "stopped before changing anything"
fi

# --- 1. Bump -------------------------------------------------------------------------------------

if [ "$bump_done" -eq 0 ]; then
  pr="$(open_pr "$bump_branch" dev)"
  if [ -z "$pr" ]; then
    worktree="$(mktemp -d)" || fail "could not create a temporary directory"
    trap 'git worktree remove --force "$worktree" >/dev/null 2>&1; rm -rf "$worktree"; git branch -D "$bump_branch" >/dev/null 2>&1' EXIT
    git worktree add --quiet -B "$bump_branch" "$worktree" refs/remotes/origin/dev \
      || fail "could not cut ${bump_branch} from origin/dev"

    (cd "$worktree" && uv version --no-sync "$version" >/dev/null) || fail "uv version ${version} failed"

    # Exactly the project's own version line in each file, and nothing a re-lock might drag along.
    changed="$(git -C "$worktree" diff --numstat | awk '{ print $3 ":" $1 "/" $2 }' | sort | tr '\n' ' ')"
    [ "$changed" = "pyproject.toml:1/1 uv.lock:1/1 " ] \
      || fail "the bump changed ${changed:-nothing}, not one line each of pyproject.toml and uv.lock — inspect ${worktree}"

    git -C "$worktree" commit --quiet -am "$title" || fail "could not commit the bump"
    git -C "$worktree" push --quiet --force-with-lease -u origin "$bump_branch" \
      || fail "could not push ${bump_branch}"
    gh pr create --repo "$slug" --base dev --head "$bump_branch" --title "$title" \
      --body "Bump the scenewise version to ${version}." >/dev/null \
      || fail "could not open the bump pull request"
    pr="$(open_pr "$bump_branch" dev)"
    [ -n "$pr" ] || fail "opened the bump pull request but could not find it"
  fi
  watch_checks "$pr"
  say "squash-merging the bump, #${pr}, onto dev"
  gh pr merge "$pr" --repo "$slug" --squash --admin --delete-branch >/dev/null \
    || fail "could not merge #${pr} onto dev"
  fetch
  [ "$(version_at refs/remotes/origin/dev)" = "$version" ] \
    || fail "#${pr} is merged but origin/dev does not carry ${version}"
fi

# --- 2. Publish onto main ------------------------------------------------------------------------

if [ "$publish_done" -eq 0 ]; then
  dev_tip="$(git rev-parse refs/remotes/origin/dev)"
  watch_run publish-main.yml ".headSha == \"${dev_tip}\"" "dev ${dev_tip:0:12}"

  git fetch --quiet origin publish || fail "could not fetch the publish branch"
  [ "$(git log -1 --format='%(trailers:key=Published-from,valueonly)' refs/remotes/origin/publish | tr -d '[:space:]')" = "$dev_tip" ] \
    || fail "the publish branch does not carry dev ${dev_tip:0:12}"
  [ "$(version_at refs/remotes/origin/publish)" = "$version" ] \
    || fail "the publish branch does not carry ${version}"

  pr="$(open_pr publish main)"
  if [ -z "$pr" ]; then
    gh pr create --repo "$slug" --base main --head publish \
      --title "$(git log -1 --format=%s refs/remotes/origin/publish)" \
      --body "Publication of dev \`${dev_tip}\` onto main, built by \`harness-scripts/publish-main.sh\`, for release ${version}." >/dev/null \
      || fail "could not open the publication pull request"
    pr="$(open_pr publish main)"
    [ -n "$pr" ] || fail "opened the publication pull request but could not find it"
  fi
  watch_checks "$pr"
  # Rebase and merge, never anything else: publish-main.sh → MERGE IT WITH "REBASE AND MERGE".
  say "rebase-merging the publication, #${pr}, onto main"
  gh pr merge "$pr" --repo "$slug" --rebase --admin >/dev/null || fail "could not merge #${pr} onto main"
  fetch
  [ "$(version_at refs/remotes/origin/main)" = "$version" ] \
    || fail "#${pr} is merged but origin/main does not carry ${version}"
fi

# --- 3. Tag --------------------------------------------------------------------------------------

target=""
while read -r sha; do
  if [ "$(version_at "$sha")" = "$version" ]; then
    target="$sha"
    break
  fi
done < <(git rev-list --first-parent --reverse refs/remotes/origin/main)
[ -n "$target" ] || fail "version ${version} was never published to origin/main's first-parent line, so there is nothing to tag"
target_line="$(git log -1 --format='%h %s' "$target")"

existing="$(git rev-parse --verify --quiet "refs/tags/${tag}^{commit}")"
if [ -n "$existing" ] && [ "$existing" != "$target" ]; then
  fail "${tag} already exists on $(git log -1 --format='%h %s' "$existing"), but ${version} resolves to ${target_line} — refusing to move it"
fi
if [ -z "$existing" ]; then
  git tag -a "$tag" -m "scenewise ${version}" "$target" || fail "could not create ${tag} at ${target_line}"
  say "created ${tag} at ${target_line}"
fi
if [ -z "$(git ls-remote --tags origin "refs/tags/${tag}")" ]; then
  git push --quiet origin "refs/tags/${tag}" || fail "could not push ${tag} to origin"
  say "pushed ${tag}"
fi

# --- 4. GitHub Release ---------------------------------------------------------------------------

gh release create "$tag" --repo "$slug" --verify-tag --title "scenewise ${version}" --generate-notes >/dev/null \
  || fail "could not create the GitHub Release for ${tag}"
say "released ${version}: https://github.com/${slug}/releases/tag/${tag}"
