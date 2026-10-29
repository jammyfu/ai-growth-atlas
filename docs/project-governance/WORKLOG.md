# WORKLOG.md

## 2026-10-29

- Added stars/day rankings (week, month, year; total last) from the GitHub API (`stargazers/history`).
- Added star-history SVG per project, five-language READMEs with a switcher, daily workflow, CI workflow, local script and docs.
- Found that `GET /repos/{r}/stargazers` now returns 404 for non-admins (GitHub change, July 2026), so `starred_at` is unavailable; switched to `stargazers/history`.
- Verification: `python3 tools/verify.py` green; real run against the API for all 8 projects.
- Next: owner review and merge; confirm first scheduled run.
