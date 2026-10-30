# CURRENT_PLAN.md

## Plan ID

PLAN-001

## Goal

Align `github-risers` with the CoderSkills harness (`continuous-project-loop`, `multi-project-program-management`) without touching rankings, translations, GEO files or the slim README.

## In Scope

- Plan files and governance records that are accurate and rollable (`CURRENT_PLAN.md`, `MASTER_PLAN.md`, `TODO_BACKLOG.md`, `docs/project-governance/*`)
- The loop rules written into repo files, not only into chat (`AGENTS.md`, `docs/AUTOMATION_COMMANDS.md`, `docs/LONG_RUNNING_AUTONOMY.md`)
- `tools/next_plan.py --check` plus regression tests for the verify and local-daily entry points (`tests/test_harness.py`)

## Out of Scope

- Ranking logic, categories, the ⚠ suspected-crack rules, `data/`, `latest/`, `rankings/`, generated READMEs
- The translation library, glossary, GEO files (`docs/index.html`, `llms.txt`, `CITATION.cff`, FAQ, FACTS, social preview)
- Any new telemetry, any data not coming from the GitHub API

## Tasks

- [x] Audit the repo against `skills/continuous-project-loop/SKILL.md` and `skills/multi-project-program-management/SKILL.md`; list the gaps in `docs/project-governance/DECISIONS.md`
- [x] Replace the stale plan, master plan, backlog, acceptance, worklog, decisions and changelog with the current state
- [x] Put the dirty-worktree rule, the record order and the verify hardening rule into `AGENTS.md` and `docs/`
- [x] Add `python3 tools/next_plan.py --check` (planning rules) and `tests/test_harness.py` (required files, plan shape, rolling, verify and local_daily hardening)
- [ ] Owner reviews the PR; merge only with approval

## Verification

- `python3 tools/verify.py`
- `python3 tools/next_plan.py --check`

## Next Candidates

- Thin Developer Tools / Design / Data new-repo boards: see `TODO_BACKLOG.md`
- Acceleration column (this week vs the week before)
