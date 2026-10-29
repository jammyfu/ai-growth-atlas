# CURRENT_PLAN.md

## Plan ID

PLAN-001

## Goal

Ship growth rankings, five-language READMEs and daily update automation, with all numbers from the GitHub API.

## In Scope

- stars/day (7/30/365) from `stargazers/history`; ranking order week, month, year, total last
- star-history SVG per project; zero telemetry
- README.md (en), README.zh-Hans.md, README.zh-Hant.md, README.ja.md, README.ko.md with switcher
- `.github/workflows/daily-update.yml`, `tools/local_daily.sh`, `docs/DAILY_UPDATE.md`

## Out of Scope

- New projects, editorial notes, per-user stargazer data

## Tasks

- [x] Fetch and compute growth from the GitHub API (`tools/update_stars.py`)
- [x] Render five READMEs (`tools/render_readme.py`)
- [x] Daily workflow, CI workflow, local script, docs
- [x] Tests and `tools/verify.py` green; real run committed
- [x] Owner reviews and merges the PR (#1)
- [x] Dual-midnight schedule (Beijing + LA), top 20, 20+ projects (PLAN-001 follow-up)
- [ ] Owner reviews and merges the follow-up PR

## Verification

- `python3 tools/verify.py`

## Next Candidates

- Acceleration column from snapshots
- Candidate discovery
