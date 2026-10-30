# PROJECT_BRIEF.md

## Project

`github-risers`

## One-line definition

Open-source projects ranked by star growth speed (stars/day), grouped by category — AI first — with 7-day newcomers and week / month / year / total boards.

## Why

Total-star lists let old projects stay on top; newly rising projects get buried. All numbers are pulled from the GitHub API daily at Beijing and Los Angeles midnight.

## First goals

- Stars/day per tracked project for week, month, year, from `stargazers/history`
- Category boards (AI primary, then developer tools, security, web/frontend, infrastructure, design/creative, data)
- Per-category 7-day newcomers via GitHub search (topic-only; repo must carry a category topic; suspected cracked/pirated repos ranked last, never leaders)
- English-first README plus zh-Hans, zh-Hant, ja, ko with a switcher on top
- Star history curve (star-history SVG); zero telemetry
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

### verify

python3 tools/verify.py
