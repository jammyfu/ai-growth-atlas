# WORKLOG.md

## 2026-10-29

- Added stars/day rankings (week, month, year; total last) from the GitHub API (`stargazers/history`).
- Added star-history SVG per project, five-language READMEs with a switcher, daily workflow, CI workflow, local script and docs.
- Found that `GET /repos/{r}/stargazers` now returns 404 for non-admins (GitHub change, July 2026), so `starred_at` is unavailable; switched to `stargazers/history`.
- Verification: `python3 tools/verify.py` green; real run against the API for all 8 projects.
- Next: owner review and merge; confirm first scheduled run.

## 2026-10-30

- Daily update now runs at Beijing 00:00 (`0 16 * * *`) and Los Angeles 00:00 (`0 7 * * *` + `0 8 * * *`, guarded by `tools/schedule_guard.py`).
- `tools/local_daily.sh --slot beijing|la`, two launchd agents and docs synced.
- Rankings show the top 20; tracked projects grew from 8 to 22 (14 added, all fetched OK from the API).
- Verification: `python3 tools/verify.py` green (32 tests).
- Added per-slot history `rankings/<date>/<slot>/`, `latest/`, history index `rankings/README.md`; first real snapshot `cn-0000` for 2026-10-30. The `pt-0000` folder appears with the first real Los Angeles run (not back-filled).
- Verification: `python3 tools/verify.py` green (43 tests).

## 2026-10-30 (new arrivals)

- Added the "hottest new repos (last 7 days)" ranking (`tools/newcomers.py`, `docs/NEW_ARRIVALS.md`), rediscovered on every slot run, stored in each snapshot (`newcomers`), `latest/` and all five READMEs.
- Dedup: excludes tracked projects and anything in the week/month/year/total top 20; enforced by tests on committed data and every snapshot.
- Verification: `python3 tools/verify.py` green (59 tests).

## 2026-10-30 (i18n follow-up)

- Hand-written translations of the new-repo descriptions in `data/newcomer_i18n.json` (zh-Hans, zh-Hant, ja, ko; en for CJK sources); used only while `src` matches the current description, otherwise the original shows. `tools/newcomer_i18n.py` lists gaps (`--strict` exits 1); the daily run prints the gap count.
- Ranking pages are generated per language: `rankings/README.<lang>.md`, `latest/rankings.<lang>.md`, `rankings/<date>/<slot>/rankings.<lang>.md`; each README links to its own language. English pages are byte-identical to before.
- Verification: `python3 tools/verify.py` green (76 tests).
