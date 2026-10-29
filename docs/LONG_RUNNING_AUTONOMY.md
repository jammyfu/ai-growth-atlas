# LONG_RUNNING_AUTONOMY.md

For scheduled and long-running agents working on this repo.

## Single plan entry

- `CURRENT_PLAN.md`

## Fixed order after each wake-up

1. Read `AGENTS.md`, `PROJECT_BRIEF.md`, `MASTER_PLAN.md`, `CURRENT_PLAN.md`
2. Finish the current minimal closed loop
3. Run `python3 tools/verify.py`
4. Update `docs/project-governance/WORKLOG.md`, `DECISIONS.md`, `CHANGELOG.md`
5. If the plan is complete, run `python3 tools/next_plan.py` and hand-edit the draft

## Rules

- No parallel plan entry points
- Data comes from the GitHub API only; never hand-edit `data/stats.json` or generated READMEs
- Zero telemetry
- Open pull requests; do not merge to `main` without the owner's approval
- Do not claim done without a green `tools/verify.py`
