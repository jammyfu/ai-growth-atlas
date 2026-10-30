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
