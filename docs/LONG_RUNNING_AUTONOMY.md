# LONG_RUNNING_AUTONOMY.md

For scheduled and long-running agents working on this repo.

## Single plan entry

- `CURRENT_PLAN.md`

## Fixed order after each wake-up

1. Read `AGENTS.md`, `PROJECT_BRIEF.md`, `MASTER_PLAN.md`, `CURRENT_PLAN.md`
2. Finish the current minimal closed loop
3. Run `python3 tools/verify.py`
4. Record: `CURRENT_PLAN.md`, `TODO_BACKLOG.md`, `docs/project-governance/WORKLOG.md`, `DECISIONS.md`; `CHANGELOG.md` only when users can see the change
5. If the plan is complete, run `python3 tools/next_plan.py`, hand-edit the draft, then `python3 tools/next_plan.py --check`

## Rules

- No parallel plan entry points
- Data comes from the GitHub API only; never hand-edit `data/stats.json` or generated READMEs
- Zero telemetry
- Open pull requests; do not merge to `main` without the owner's approval
- Do not claim done without a green `tools/verify.py`

## Dirty worktree rule

- If a wake-up starts with uncommitted changes, deal with them first: if they already form a closed loop, `verify` and open a PR; if not, finish or park them in `WORKLOG.md` and stop. Do not stack a new task on top.
- The only automated writer of `data/`, `latest/`, `rankings/` and `README*.md` is the daily job; `tools/local_daily.sh` refuses to run on a dirty tree or off `main` and uses its own PATH and `python3` path.
- `tools/verify.py` runs with `sys.executable`, never `shell=True` and never a bare `python`/`pytest` (`tests/test_harness.py`).
- The daily data run (Actions `schedule` / `workflow_dispatch`, or `tools/local_daily.sh` with `RISERS_DAILY_RUN=1`) skips the doc-state checks in `tests/test_harness.py`, so a stale plan file can never block a data update; CI runs them on every pull request.
