#!/usr/bin/env bash
# Local daily update: fetch real star data, regenerate READMEs, verify, commit and push.
# Slots (match the Actions schedule): --slot beijing runs only at 00:xx Asia/Shanghai,
# --slot la runs only at 00:xx America/Los_Angeles (DST-aware), no --slot runs always.
# Each run is also archived under rankings/<date>/<cn-0000|pt-0000|manual-HHMM>/ and copied to latest/.
# Every run also re-discovers per-category 7-day new-repo rankings via the search API (several minutes).
# Use this when GitHub Actions cannot run (billing, quota, outage). Reads GITHUB_TOKEN;
# if unset it falls back to `gh auth token`. Safe for cron/launchd (sets its own PATH).
#
#   tools/local_daily.sh            # update, verify, commit, push to origin/main
#   tools/local_daily.sh --no-push  # update, verify, commit locally only
#   tools/local_daily.sh --slot la  # only proceed if it is currently 00:xx in Los Angeles
#
# Copy: this local run also translates new-repo descriptions and polishes copy with Google Antigravity CLI
# (`agy`, your signed-in session; model POLISH_MODEL, default gemini-3.8-flash-medium) when agy is installed.
# Without agy, or if anything fails, those steps are skipped and the update goes on. Set I18N_POLISH=0 to
# turn polish off. See docs/I18N_PIPELINE.md.
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
cd "$(dirname "$0")/.."

PUSH=1
SLOT=""
UPDATE_SLOT=auto
while [ $# -gt 0 ]; do
  case "$1" in
    --no-push) PUSH=0 ;;
    --slot) SLOT="${2:-}"; shift ;;
    *) echo "error: unknown argument $1" >&2; exit 2 ;;
  esac
  shift
done

PY="$(command -v python3)"

# Time-slot guard first: cheap, needs no token and touches nothing. ATLAS_NOW_UTC overrides the clock for tests.
case "$SLOT" in
  "") UPDATE_SLOT=auto ;;
  beijing) "$PY" tools/schedule_guard.py --tz Asia/Shanghai --hour 0 || exit 0; UPDATE_SLOT=cn ;;
  la) "$PY" tools/schedule_guard.py --tz America/Los_Angeles --hour 0 || exit 0; UPDATE_SLOT=pt ;;
  *) echo "error: --slot must be beijing or la" >&2; exit 2 ;;
esac

if [ -z "${GITHUB_TOKEN:-}" ]; then
  if command -v gh >/dev/null 2>&1; then
    GITHUB_TOKEN="$(gh auth token)"
    export GITHUB_TOKEN
  else
    echo "error: set GITHUB_TOKEN (or install and log in to gh)" >&2
    exit 2
  fi
fi

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

# doc-state tests (plan files, governance) must not block the data update; CI still runs them on every PR
export RISERS_DAILY_RUN=1
export I18N_POLISH="${I18N_POLISH:-1}" I18N_TRANSLATE_BACKEND="${I18N_TRANSLATE_BACKEND:-agy}" I18N_POLISH_BACKEND=agy
"$PY" tools/update_stars.py --slot "$UPDATE_SLOT"
"$PY" tools/verify.py

if [ -z "$(git status --porcelain)" ]; then
  echo "No changes."
  exit 0
fi
git add data rankings latest README*.md docs/HOW_IT_WORKS*.md docs/DETAILS*.md
git commit -m "chore(data): daily star update $(date -u +%F)"
if [ "$PUSH" = 1 ]; then
  git push origin main
fi
