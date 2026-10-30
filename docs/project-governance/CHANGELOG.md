# CHANGELOG.md

## 2026-10-29

- Rankings by stars/day (week, month, year) with total stars last, all from the GitHub API.
- Star history curve per project.
- READMEs in English, 简体中文, 繁體中文, 日本語, 한국어 with a language switcher.
- Daily update workflow and local script; removed unverifiable `stars_note` text.

## 2026-10-30

- Daily update at Beijing 00:00 and Los Angeles 00:00 (DST-aware).
- Every ranking shows the top 20; 22 projects tracked.
- Ranking history per time slot, `latest/`, and a history index linked from every README.
- New ranking: hottest new repos created in the last 7 days (search API, deduplicated against all other rankings).

## 2026-10-30 (i18n pipeline)

- All 39 untranslated new-repo descriptions translated into zh-Hans, zh-Hant, ja, ko (+ en for the 11 Chinese sources); every project blurb and category description already had all five languages (now enforced by a test).
- `tools/i18n_pipeline.py` + `tools/llm.py`: the scheduled update translates new descriptions into the cache (skipping anything already translated) in CI (Cursor CLI, optional `CURSOR_API_KEY` secret). Polish runs locally with the Antigravity CLI (`agy`, model `gemini-3.8-flash-medium`) via `tools/polish_local.sh` / `tools/local_daily.sh`. A failure keeps the existing text and never blocks the update.

## 2026-10-30 (translation library, slim README)

- `data/newcomer_i18n.json` became the translation library `data/translation_library.json`, keyed by repo + source-text hash + language. A hit costs no model call; only new or changed descriptions are translated, only missing languages are asked for; every run logs hits/new. Tests prove zero model calls on a full hit.
- `data/glossary.json`: fixed terms for common words; only the terms present in a batch go into the prompt. Polish sends only un-polished entries and logs how many were skipped.
- READMEs in all five languages are now a first screen: headline, one sentence, update stamp, the category leaders table (rows link to the category boards), then the category boards. Intro, schedule, "how it is produced", categories table and contributing moved to generated `docs/HOW_IT_WORKS*.md`; the long new-repo explanation moved there too.
- README first screen reworked (generator only): first line `GitHub 涨星榜 / GitHub Risers` (English: `GitHub Risers: Ranked by Stars Gained per Day`), header image `.github/social-preview.png`, three badges (MIT, CI, last updated), website link, three Q&A subheads linking `docs/FAQ.md`, a star prompt, a "how to cite" line (`CITATION.cff`) and a link to `docs/FACTS.md`. Each board shows the top 10 in the README; the full top 20 stays in `latest/`. Those linked files come from the GEO pull request (#9); the generator only links them, and a test checks the FAQ anchors.
