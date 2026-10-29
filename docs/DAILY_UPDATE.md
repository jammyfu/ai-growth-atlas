# Daily update

Everything the atlas shows comes from the GitHub API (`tools/update_stars.py`). Nothing is estimated; a
project that cannot be fetched is listed under "Missing data" in the README.

## What a run does

1. `GET /repos/{owner}/{repo}` → `stargazers_count`, `created_at`.
2. `GET /repos/{owner}/{repo}/stargazers/history` (newest week first, 30 weeks per page) until one year is covered.
3. Writes `data/stats.json` (growth per project), appends today's star count to `data/stars.json`
   (snapshots, used for cross-checks over time), then regenerates the five READMEs.

Why `stargazers/history` and not `stargazers` + `starred_at`: since July 2026 GitHub returns 404 for
`GET /repos/{owner}/{repo}/stargazers` unless you are an admin or collaborator of the repo
([changelog](https://github.blog/changelog/2026-06-30-upcoming-access-restrictions-to-public-api-endpoints-and-ui-views/)).
The privacy-safe replacement is `stargazers/history`, which returns daily counts without user identities
([changelog](https://github.blog/changelog/2026-09-04-new-api-endpoint-provides-privacy-safe-star-history-data/)).
Cross-check built into the tests: for every repo whose full history was read, the sum of the history equals `stargazers_count`.

## Option A: GitHub Actions (preferred when it runs)

`.github/workflows/daily-update.yml` runs at 02:17 UTC every day (and on manual dispatch), regenerates the
data, runs `tools/verify.py`, and commits to `main` if anything changed. It uses only first-party
`actions/*` and the built-in `GITHUB_TOKEN`.
`.github/workflows/ci.yml` runs `tools/verify.py` on every pull request (no network).

Scheduled workflows run from the default branch only, so the schedule starts after this is merged.

### Can Actions run for this account? (checked 2026-10-29)

The account has a billing problem, but it only affects private repos:

| Check | Result |
|---|---|
| `gh api repos/jammyfu/ai-growth-atlas --jq .private` | `false` (public repo; standard hosted runners are free for public repos) |
| `gh api repos/jammyfu/ai-growth-atlas/actions/permissions` | `{"enabled":true,"allowed_actions":"all"}` |
| Latest run of a **private** repo (`jammyfu/Tallyo`, run 40579601597, 2026-10-27) | failed in 3 s: "The job was not started because recent account payments have failed or your spending limit needs to be increased." |
| Latest run of a **public** repo (`jammyfu/open-game-skills`, run 40870933400, 2026-10-29) | `success`, ran 80 s on a GitHub-hosted runner |

So Actions should work here because the repo is public. If the repo is ever made private, or GitHub starts
blocking public repos too, the daily job will fail with the same payment message. Re-check with:

```bash
gh api repos/jammyfu/ai-growth-atlas/actions/runs --jq '.workflow_runs[:5][]|[.created_at,.name,.conclusion]|@tsv'
# a payment failure shows up in the job annotation:
gh api repos/jammyfu/ai-growth-atlas/check-runs/<job_id>/annotations --jq '.[].message'
```

## Option B: local script (always works)

```bash
GITHUB_TOKEN=$(gh auth token) python3 tools/update_stars.py   # fetch + render only
tools/local_daily.sh              # update, verify, commit, push to main
tools/local_daily.sh --no-push    # update, verify, commit locally
```

`tools/local_daily.sh` reads `GITHUB_TOKEN` (falls back to `gh auth token`), refuses to run off `main` or
with a dirty tree, and sets its own `PATH` so it works from cron/launchd.

### cron (Linux / macOS)

```cron
17 10 * * *  cd /path/to/ai-growth-atlas && GITHUB_TOKEN=ghp_xxx tools/local_daily.sh >> /tmp/atlas-daily.log 2>&1
```

Do not commit the token. Keep it in the crontab line, or leave `GITHUB_TOKEN` unset and rely on `gh auth login`.

### launchd (macOS)

Copy `docs/launchd/com.jammyfu.ai-growth-atlas.daily.plist`, replace `/PATH/TO` with the clone path, then:

```bash
cp docs/launchd/com.jammyfu.ai-growth-atlas.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jammyfu.ai-growth-atlas.daily.plist
launchctl start com.jammyfu.ai-growth-atlas.daily   # test run
```

The plist runs at 10:17 local time. It relies on `gh auth login` for the token (launchd has no shell profile).

## Verify

```bash
python3 tools/verify.py
```
