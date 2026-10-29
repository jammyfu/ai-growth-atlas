#!/usr/bin/env bash
# Local daily update: fetch real star data, regenerate READMEs, verify, commit and push.
# Use this when GitHub Actions cannot run (billing, quota, outage). Reads GITHUB_TOKEN;
# if unset it falls back to `gh auth token`. Safe for cron/launchd (sets its own PATH).
#
#   tools/local_daily.sh            # update, verify, commit, push to origin/main
#   tools/local_daily.sh --no-push  # update, verify, commit locally only
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
cd "$(dirname "$0")/.."

PUSH=1
[ "${1:-}" = "--no-push" ] && PUSH=0

if [ -z "${GITHUB_TOKEN:-}" ]; then
  if command -v gh >/dev/null 2>&1; then
    GITHUB_TOKEN="$(gh auth token)"
    export GITHUB_TOKEN
  else
    echo "error: set GITHUB_TOKEN (or install and log in to gh)" >&2
    exit 2
  fi
fi

PY="$(command -v python3)"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "main" ]; then
  echo "error: run on main (currently on $branch)" >&2
  exit 3
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "error: working tree not clean; refusing to run" >&2
  exit 3
fi
git pull --ff-only

"$PY" tools/update_stars.py
"$PY" tools/verify.py

if [ -z "$(git status --porcelain)" ]; then
  echo "No changes."
  exit 0
fi
git add data README*.md
git commit -m "chore(data): daily star update $(date -u +%F)"
if [ "$PUSH" = 1 ]; then
  git push origin main
fi
