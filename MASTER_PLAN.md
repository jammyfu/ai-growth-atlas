# MASTER_PLAN.md

## Goal

A trustworthy ranking of fast-rising GitHub repositories by stars gained per day, grouped by category (AI first), refreshed twice a day from the GitHub API and readable in five languages.

## Current phase

Phase 4: harness and upkeep (Phases 1-3 are done and merged).

## Phases

### Phase 1: Structure (done)
- Project list, short descriptions, five languages

### Phase 2: Growth data and automation (done)
- stars/day for 7/30/365 days from `stargazers/history`
- Daily update (Actions + local fallback) at Beijing 00:00 and Los Angeles 00:00, per-slot history, `latest/`
- Top-20 boards, 7-day newcomers board

### Phase 3: Categories, i18n pipeline, discovery (done)
- Rebrand to `github-risers`; categories ai (primary), devtools, security, web, infra, design, data; 70 tracked projects
- Per-category newcomers by topic only; suspected cracked/pirated repos flagged, ranked last, never leaders
- Translation library + glossary, slim README first screen, GEO (Pages, `llms.txt`, `CITATION.cff`, FAQ, FACTS)

### Phase 4: Harness and upkeep (now)
- Plan and governance files follow `jammyfu/CoderSkills` (`continuous-project-loop`, `multi-project-program-management`)
- Thin boards (Developer Tools quality, Design, Data) and the acceleration column: see `TODO_BACKLOG.md`

## Definition of done for a phase

- `python3 tools/verify.py` passes; data in `data/stats.json` came from a real run
- A daily update has run unattended at both the Beijing and Los Angeles slots

## Questions for next review

- Should the year ranking keep dividing young repos by their age (current behaviour, flagged with †)?
- Which projects should be added or retired?
- Is a quality signal (beyond topics and the ⚠ rules) wanted for the Developer Tools new-repo board?
