# TODO_BACKLOG.md

## Now

- [ ] Confirm the first unattended cron runs after the merge: `cn-0000` (Beijing) and `pt-0000` (Los Angeles) folders appear under `rankings/<date>/` (`gh run list --workflow daily-update.yml`)
- [ ] Developer Tools new-repo board: 15 of 20 entries were flagged ⚠ in the last run because star-farmed repos use `cli` / `developer-tools`; decide whether to add a quality signal (owner call)
- [ ] Design and Data new-repo boards are thin (0-2 entries): widen with specific topics only (no generic ones; `tests/test_spam.py` guards that)

## Next

- [ ] Acceleration column (stars/day this week vs. previous week) from `data/stars.json` snapshots
- [ ] Add more tracked projects (needs five-language `desc`)

## Later

- [ ] Candidate discovery for tracked projects with owner approval

## Risks / Blockers

- [ ] GitHub may change or rate-limit `stargazers/history` (documented max 30 weeks/page, page <= 100)
- [ ] If Actions cannot run (billing, quota), use `tools/local_daily.sh`
- [ ] The search API is index-based and can lag by minutes; thin categories can be empty in one run
