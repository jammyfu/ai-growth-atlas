# AGENTS.md

Project harness follows `jammyfu/CoderSkills` → `skills/continuous-project-loop` and `skills/multi-project-program-management`.

- Single plan entry: `CURRENT_PLAN.md`. Long-term route: `MASTER_PLAN.md`. Candidates: `TODO_BACKLOG.md`. Records: `docs/project-governance/`.
- Verify before claiming done: `python3 tools/verify.py` (explicit interpreter, no PATH reliance).
- Star data must come from the GitHub API only (`python3 tools/update_stars.py`). Never type or estimate numbers; mark missing data as missing.
- Never edit the generated files by hand: `README*.md`, `docs/HOW_IT_WORKS*.md`, `data/stats.json`, `latest/`, `rankings/` (history snapshots are append-only; never edit or delete them by hand). Edit `data/projects.json`, `data/categories.json`, `tools/i18n.py`, then re-run the tools.
- Zero telemetry: no analytics, tracking or beacon scripts, ever.
- `data/projects.json` `desc` and `data/categories.json` `name`/`desc` need all five languages: en, zh-Hans, zh-Hant, ja, ko.
- Changes go through pull requests. Do not push or merge to `main` without the owner's approval (the daily workflow/script is the only automated writer of `data/` and `README*`).
- Generated too: `rankings/README*.md`, `latest/rankings*.md`, `rankings/<date>/<slot>/rankings.<lang>.md` (all from `tools/i18n.py` + `stats.json`). Translations of new-repo descriptions live in the translation library `data/translation_library.json` (repo + source hash + language; fixed terms in `data/glossary.json`); list the gaps and the hit rate with `python3 tools/newcomer_i18n.py`. The README is only a first screen (top 10 per board; the full top 20 is in `latest/`; it links `docs/FAQ.md`, `docs/FACTS.md`, `CITATION.cff`, `.github/social-preview.png`, which the GEO work owns: never generate or overwrite them from the generator) (headline, one sentence, this round's #1s, the boards): change its wording in `tools/i18n.py` / `tools/render_readme.py`, and put explanations in `render_docs` (`docs/HOW_IT_WORKS*.md`).
- The "hottest new repos (7 days)" ranking is discovered by `tools/newcomers.py` from the search API; it must never repeat a project from another ranking (see `docs/NEW_ARRIVALS.md`).

- Categories (AI primary + others) are defined in `data/categories.json` and documented in `docs/CATEGORIES.md`. Newcomers are per-category; see `docs/NEW_ARRIVALS.md`.
