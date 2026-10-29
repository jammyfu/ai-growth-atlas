# PROJECT_BRIEF.md

## Project

`ai-growth-atlas`

## One-line definition

AI projects ranked by star growth speed (stars/day over 7, 30 and 365 days), with the all-time star ranking last.

## Why

Total-star lists let old projects stay on top; newly rising projects get buried. All numbers are pulled from the GitHub API daily.

## First goals

- Stars/day per project for week, month, year, from `stargazers/history`
- English-first README plus zh-Hans, zh-Hant, ja, ko with a switcher on top
- Star history curve (star-history SVG) for every project; zero telemetry
- Daily update by GitHub Actions, with a local script fallback

## Non-goals

- Editorial claims about why a project is rising (not verifiable from the API)
- Per-user stargazer data (GitHub no longer exposes it publicly)

## Execution files

- `CURRENT_PLAN.md`: the only current plan
- `MASTER_PLAN.md`: long-term route
- `TODO_BACKLOG.md`: candidates
- `docs/project-governance/WORKLOG.md`: round records

### lint

python3 -m compileall -q tools tests

### test

python3 -m unittest discover -s tests

### build

python3 tools/render_readme.py --check
