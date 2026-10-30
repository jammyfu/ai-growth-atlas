#!/usr/bin/env bash
# Polish the copy (project blurbs + translated new-repo descriptions) with Google Antigravity CLI (`agy`)
# on YOUR machine, then render, verify and commit. CI never runs this: it only translates.
#
#   tools/polish_local.sh --check-models   # list the models agy offers and say whether the one we pin is there
#   tools/polish_local.sh --dry-run        # count what would be polished, call nothing
#   tools/polish_local.sh --limit 6        # polish at most 6 texts (a first, small real run)
#   tools/polish_local.sh                  # polish everything pending, verify, commit locally
#   tools/polish_local.sh --push           # ... and push the commit
#   tools/polish_local.sh --targets projects,newcomers,categories   # what to polish (default: projects,newcomers)
#
# Model: POLISH_MODEL, default gemini-3.8-flash-medium (the exact slug must be in `agy models`; nothing is
# substituted). Auth: your signed-in `agy` session (run `agy` once interactively to sign in). No key is stored in
# the repo; the script never reads or prints credentials. Every agy call runs in an empty temp directory.
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
cd "$(dirname "$0")/.."

MODEL="${POLISH_MODEL:-gemini-3.8-flash-medium}"
export POLISH_MODEL="$MODEL" I18N_POLISH_BACKEND=agy
PUSH=0; DRY=0; CHECK=0; ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --push) PUSH=1 ;;
    --dry-run) DRY=1; ARGS+=(--dry-run) ;;
    --check-models) CHECK=1 ;;
    --limit) ARGS+=(--limit "${2:?--limit needs a number}"); shift ;;
    --targets) ARGS+=(--targets "${2:?--targets needs a list}"); shift ;;
    *) echo "error: unknown argument $1" >&2; exit 2 ;;
  esac
  shift
done

if ! command -v agy >/dev/null 2>&1; then
  echo "error: agy not found. Install: curl -fsSL https://antigravity.google/cli/install.sh | bash" >&2
  exit 2
fi

if [ "$CHECK" = 1 ]; then
  echo "== agy models =="
  out="$(agy models 2>&1)" || true
  echo "$out"
  echo
  if echo "$out" | grep -qi '^error'; then
    echo "agy could not list models (not signed in? run \`agy\` once interactively to sign in)." >&2
    exit 1
  fi
  if echo "$out" | awk '{print $1}' | grep -qx "$MODEL"; then
    echo "OK: $MODEL is available."
  else
    echo "NOT AVAILABLE: $MODEL is not in the list above. Nothing will be substituted;" >&2
    echo "pick an exact slug from the list and run with POLISH_MODEL=<slug>." >&2
    exit 1
  fi
  exit 0
fi

PY="$(command -v python3)"
if [ "$DRY" = 0 ]; then
  if [ -n "$(git status --porcelain)" ]; then
    echo "error: working tree not clean; refusing to run" >&2
    exit 3
  fi
  if [ "$(git rev-parse --abbrev-ref HEAD)" = main ]; then git pull --ff-only; fi
fi

"$PY" tools/i18n_pipeline.py --polish ${ARGS[@]+"${ARGS[@]}"}
[ "$DRY" = 1 ] && exit 0

"$PY" tools/render_readme.py
"$PY" tools/verify.py
if [ -z "$(git status --porcelain)" ]; then
  echo "No changes."
  exit 0
fi
git add data README*.md latest rankings
git commit -m "chore(i18n): polish copy via agy ($MODEL)"
if [ "$PUSH" = 1 ]; then
  git push
else
  echo "Committed locally. Review with: git show --stat HEAD   (push with: git push)"
fi
