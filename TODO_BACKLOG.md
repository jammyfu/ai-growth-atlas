# TODO_BACKLOG.md

## Now

- [ ] Confirm the first scheduled `daily-update` run after merge (check Actions tab or `gh run list`)

## Next

- [ ] Acceleration column (stars/day this week vs. previous week) from `data/stars.json` snapshots
- [ ] Add more projects (needs five-language `desc`)

## Later

- [ ] Candidate discovery via GitHub search API with owner approval

## Risks / Blockers

- [ ] GitHub may change or rate-limit `stargazers/history` (documented max 30 weeks/page, page ≤ 100)
- [ ] If the repo becomes private, Actions fails on the account billing problem; use `tools/local_daily.sh`
