# AGENTS.md

Project harness follows `jammyfu/CoderSkills` → `skills/continuous-project-loop` and `skills/multi-project-program-management`.

- Single plan entry: `CURRENT_PLAN.md`. Long-term route: `MASTER_PLAN.md`. Candidates: `TODO_BACKLOG.md`. Records: `docs/project-governance/`.
- Verify before claiming done: `python3 tools/verify.py` (explicit interpreter, no PATH reliance).
- Star data must come from the GitHub API only (`python3 tools/update_stars.py`). Never type or estimate numbers; mark missing data as missing.
- Never edit the generated files by hand: `README*.md`, `data/stats.json`. Edit `data/projects.json`, `data/categories.json`, `tools/i18n.py`, then re-run the tools.
- Zero telemetry: no analytics, tracking or beacon scripts, ever.
- `data/projects.json` `desc` and `data/categories.json` `name`/`desc` need all five languages: en, zh-Hans, zh-Hant, ja, ko.
- Changes go through pull requests. Do not push or merge to `main` without the owner's approval (the daily workflow/script is the only automated writer of `data/` and `README*`).
