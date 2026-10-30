# AUTOMATION_COMMANDS.md

## Current plan entry

- `CURRENT_PLAN.md`

## Verify

```bash
python3 tools/verify.py
```

## Roll to the next plan

```bash
python3 tools/next_plan.py          # roll a finished plan forward (draft: edit it by hand)
python3 tools/next_plan.py --check  # validate CURRENT_PLAN.md: one Goal, 3-7 tasks, Out of Scope, Next Candidates
```

## Refresh star data (GitHub API)

```bash
GITHUB_TOKEN=$(gh auth token) python3 tools/update_stars.py
python3 tools/update_stars.py --slot cn   # cn|pt|manual|auto; archives to rankings/<date>/<slot>/ and latest/
python3 tools/render_readme.py          # re-render only (READMEs, latest/, rankings/README*.md, per-language snapshot pages)
python3 tools/newcomer_i18n.py          # list new-repo descriptions that still lack a translation (--strict: exit 1)
tools/local_daily.sh --no-push          # full local daily cycle, commit but do not push
```

## Recommended order for automation agents

1. Read `CURRENT_PLAN.md`, `MASTER_PLAN.md`, `TODO_BACKLOG.md`, `docs/project-governance/WORKLOG.md`
2. Finish the smallest closed loop
3. `python3 tools/verify.py`
4. Update the record files (`CURRENT_PLAN.md`, `TODO_BACKLOG.md`, `WORKLOG.md`, `DECISIONS.md`, `CHANGELOG.md`)
5. If the plan is complete, `python3 tools/next_plan.py`, edit the draft, `python3 tools/next_plan.py --check`

`update_stars.py` also re-discovers the 7-day new-repo ranking (about 2 minutes; rules in [NEW_ARRIVALS.md](NEW_ARRIVALS.md)).

Details of the daily job and fallbacks: [DAILY_UPDATE.md](DAILY_UPDATE.md).
