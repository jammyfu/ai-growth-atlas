# MASTER_PLAN.md

## Goal

A trustworthy, daily-refreshed ranking of fast-rising AI projects, readable in five languages.

## Current phase

Phase 2: growth rankings, i18n, daily automation.

## Phases

### Phase 1: Structure (done)
- Problem-based categories, project list, short descriptions

### Phase 2: Growth data and automation
- stars/day for 7/30/365 days from the GitHub API
- Five-language READMEs, star-history curves
- Daily update (Actions + local fallback)

### Phase 3: Discovery
- Automatically surface candidate projects from GitHub search/trending-style API queries, owner approves additions
- Acceleration (change in stars/day) column once enough snapshots exist

## Definition of done for Phase 2

- `python3 tools/verify.py` passes; data in `data/stats.json` came from a real run
- A daily update has run unattended at least once (Actions or local)

## Questions for next review

- Should the year ranking use repo age as divisor for young repos (current behaviour, flagged with †)?
- Which projects should be added or retired?
