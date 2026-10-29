# WORKLOG.md

## 2026-10-29

- Added stars/day rankings (week, month, year; total last) from the GitHub API (`stargazers/history`).
- Added star-history SVG per project, five-language READMEs with a switcher, daily workflow, CI workflow, local script and docs.
- Found that `GET /repos/{r}/stargazers` now returns 404 for non-admins (GitHub change, July 2026), so `starred_at` is unavailable; switched to `stargazers/history`.
- Verification: `python3 tools/verify.py` green; real run against the API for all 8 projects.
- Next: owner review and merge; confirm first scheduled run.

## 2026-10-30

- Daily update now runs at Beijing 00:00 (`0 16 * * *`) and Los Angeles 00:00 (`0 7 * * *` + `0 8 * * *`, guarded by `tools/schedule_guard.py`).
- `tools/local_daily.sh --slot beijing|la`, two launchd agents and docs synced.
- Rankings show the top 20; tracked projects grew from 8 to 22 (14 added, all fetched OK from the API).
- Verification: `python3 tools/verify.py` green (32 tests).
