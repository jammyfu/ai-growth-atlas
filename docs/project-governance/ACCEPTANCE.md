# ACCEPTANCE.md

## Phase 2

- Every project has stars/day for 7, 30 and 365 days or is listed as missing with the API error
- Rankings in order: week, month, year, total (last)
- Each project shows a star-history SVG in every README
- README.md is English; zh-Hans, zh-Hant, ja, ko exist; each has the switcher on its first line
- No analytics/tracking script anywhere (`tests/test_repo.py::ZeroTelemetryTests`)
- `daily-update.yml` and `tools/local_daily.sh` exist; `docs/DAILY_UPDATE.md` states whether Actions can run and why
- `python3 tools/verify.py` passes

## Phase 3: categories and newcomers

- Categories in `data/categories.json` (ai primary + 6 others), each with newcomers / week / month / year / total, total last
- New repos are found by topic only and must carry a category topic; no generic topics (`tests/test_spam.py`)
- Suspected cracked / pirated repos are listed after every normal repo, marked ⚠, and never appear in "Category leaders"
- Every scheduled entry (both Beijing and Los Angeles crons, `workflow_dispatch`, local launchd) runs `tools/update_stars.py` (`tests/test_spam.py::ScheduledPathTests`)
- README is a first screen (top 10 per board); the full top 20 is in `latest/`; GEO files exist and are linked

## Phase 4: harness

- `CURRENT_PLAN.md` passes `python3 tools/next_plan.py --check` (one Plan ID, one Goal, 3-7 tasks, Out of Scope, Verification, Next Candidates)
- `tools/verify.py` and `tools/local_daily.sh` do not depend on the shell PATH or `shell=True` (`tests/test_harness.py`)
- The harness files from `continuous-project-loop` exist and `AGENTS.md` names the two CoderSkills skills
