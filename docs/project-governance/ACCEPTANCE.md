# ACCEPTANCE.md

## Phase 2

- Every project has stars/day for 7, 30 and 365 days or is listed as missing with the API error
- Rankings in order: week, month, year, total (last)
- Each project shows a star-history SVG in every README
- README.md is English; zh-Hans, zh-Hant, ja, ko exist; each has the switcher on its first line
- No analytics/tracking script anywhere (`tests/test_repo.py::ZeroTelemetryTests`)
- `daily-update.yml` and `tools/local_daily.sh` exist; `docs/DAILY_UPDATE.md` states whether Actions can run and why
- `python3 tools/verify.py` passes
