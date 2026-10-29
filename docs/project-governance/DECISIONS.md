# DECISIONS.md

## 2026-10-29

### Use `stargazers/history`, not `stargazers` + `starred_at`

- The stargazers list is restricted to admins/collaborators since July 2026 and returns 404 for these repos.
- `stargazers/history` returns daily counts per week without identities; the full history sums exactly to `stargazers_count` for every repo checked.

### Window definition

- Gain = sum of the N complete UTC days before today (today excluded), N = 7, 30, 365. Stars/day = gain / N.
- For repos younger than N days, divide by repo age (days since `created_at`, min 1) and flag with †.

### Drop `stars_note`

- The free-text notes ("recently very fast", "always near the top") were not verifiable from API data and were removed. Rankings show measured numbers only.

### Generated files

- `README*.md` and `data/stats.json` are generated; `tests/test_repo.py` fails if READMEs are stale.
