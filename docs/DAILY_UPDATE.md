# Daily update

Everything the atlas shows comes from the GitHub API (`tools/update_stars.py`). Nothing is estimated; a
project that cannot be fetched is listed under "Missing data" in the README.

## What a run does

1. `GET /repos/{owner}/{repo}` → `stargazers_count`, `created_at`.
2. `GET /repos/{owner}/{repo}/stargazers/history` (newest week first, 30 weeks per page) until one year is covered.
3. Re-discovers the "hottest new repos (last 7 days)" ranking with the GitHub search API (about 30 search requests, paced to the 30/min limit, so a run takes roughly 2 minutes; rules in [NEW_ARRIVALS.md](NEW_ARRIVALS.md)). Every slot run (Beijing and Los Angeles, Actions or local) redoes it from scratch.
4. Writes `data/stats.json` (growth per project), archives it under `rankings/<date>/<slot>/` and `latest/`, appends today's star count to `data/stars.json`
   (snapshots, used for cross-checks over time), then regenerates the five READMEs.

Why `stargazers/history` and not `stargazers` + `starred_at`: since July 2026 GitHub returns 404 for
`GET /repos/{owner}/{repo}/stargazers` unless you are an admin or collaborator of the repo
([changelog](https://github.blog/changelog/2026-06-30-upcoming-access-restrictions-to-public-api-endpoints-and-ui-views/)).
The privacy-safe replacement is `stargazers/history`, which returns daily counts without user identities
([changelog](https://github.blog/changelog/2026-09-04-new-api-endpoint-provides-privacy-safe-star-history-data/)).
Cross-check built into the tests: for every repo whose full history was read, the sum of the history equals `stargazers_count`.

## Where results go: history per time slot

Every run stores its result in its own folder and keeps it (nothing is overwritten except a re-run of the same slot):

```
rankings/<date>/cn-0000/   Beijing 00:00 run      (date = Asia/Shanghai date)
rankings/<date>/pt-0000/   Los Angeles 00:00 run  (date = America/Los_Angeles date)
rankings/<date>/manual-HHMM/   any other run, e.g. manual dispatch (date/time = UTC)
    stats.json     full API-derived data of that run, plus a "slot" block and the new-repos ranking (`newcomers`)
    rankings.md    top-20 tables for that run, new-repos table first (English, compact)
    rankings.<lang>.md   the same page in zh-Hans, zh-Hant, ja, ko
rankings/README.md   history index linking every snapshot, newest first (README.<lang>.md per language)
latest/stats.json, latest/rankings.md   copy of the newest run (latest/rankings.<lang>.md per language)
data/stats.json      what the READMEs are rendered from (same as the newest run)
```

The five READMEs show the latest ranking and link to the history index and `latest/rankings*.md` of their own language.
The pages are generated from `tools/i18n.py` (strings) and `stats.json` (data); never edit them by hand.
`tools/update_stars.py --slot cn|pt|manual|auto` picks the folder (`auto`, the default, uses cn if it is 00:xx in
Beijing, pt if 00:xx in Los Angeles, otherwise manual). The workflow and `tools/local_daily.sh` pass the slot themselves.
`tools/verify.py` checks that `latest/`, the indexes and every snapshot's `rankings*.md` (all languages) match their data.

## New-repo description translations

The new-repos table shows the repo's own GitHub description. For each language, `data/newcomer_i18n.json`
can hold a hand-written translation, keyed by repo full name with the original text in `src`; it is shown only
while `src` still equals the current description, otherwise the original is shown. Repos new to the ranking
have no entry until someone adds one, so check the gaps with `python3 tools/newcomer_i18n.py` (the daily run
prints the count; it never fails because of it). No online translation service or key is used.

## Schedule: Beijing 00:00 and Los Angeles 00:00

| Slot | When | cron (UTC) |
|---|---|---|
| Beijing 00:00 (UTC+8, no DST) | 16:00 UTC | `0 16 * * *` |
| America/Los_Angeles 00:00, PDT (UTC-7) | 07:00 UTC | `0 7 * * *` |
| America/Los_Angeles 00:00, PST (UTC-8) | 08:00 UTC | `0 8 * * *` |

GitHub cron only knows UTC, so both LA entries fire every day. `tools/schedule_guard.py --tz America/Los_Angeles --hour 0`
checks the real Los Angeles clock and lets only the one that is actually 00:xx there continue; the other run skips
(you will see a green run whose steps are skipped). Tests cover PDT, PST, both 2026 DST changes (Mar 8, Nov 1) and
assert that exactly one of the two LA slots passes on every day of the year (`tests/test_schedule.py`).
The Beijing entry is unguarded. Manual `workflow_dispatch` always runs.

Caveat: GitHub may start scheduled runs several minutes late. A run delayed past the end of the 00:xx hour in Los Angeles
would skip. The Beijing slot and the next day's runs still refresh the data, so a delay never leaves it stale for more than a day.

## Option A: GitHub Actions (preferred when it runs)

`.github/workflows/daily-update.yml` regenerates the data, runs `tools/verify.py`, and commits to `main` if anything changed.
It uses only first-party `actions/*` and the built-in `GITHUB_TOKEN`.
`.github/workflows/ci.yml` runs `tools/verify.py` on every pull request and push to `main` (no network).

Scheduled workflows run from the default branch only.

### Can Actions run for this account? (checked 2026-10-29, re-checked 2026-10-30)

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
tools/local_daily.sh                  # update, verify, commit, push to main (any time)
tools/local_daily.sh --no-push        # update, verify, commit locally
tools/local_daily.sh --slot beijing   # only proceeds if it is 00:xx in Asia/Shanghai
tools/local_daily.sh --slot la        # only proceeds if it is 00:xx in America/Los_Angeles (DST-aware)
```

`tools/local_daily.sh` reads `GITHUB_TOKEN` (falls back to `gh auth token`), refuses to run off `main` or
with a dirty tree, and sets its own `PATH` so it works from cron/launchd. The `--slot` check runs first and exits 0
with `skip: ...` without touching anything. `ATLAS_NOW_UTC=2026-10-29T08:30:00Z` overrides the clock for testing.

### cron (Linux / macOS, machine clock in Beijing time)

```cron
0 0 * * *       cd /path/to/ai-growth-atlas && tools/local_daily.sh --slot beijing >> /tmp/atlas-daily.log 2>&1
0 15,16 * * *   cd /path/to/ai-growth-atlas && tools/local_daily.sh --slot la      >> /tmp/atlas-daily.log 2>&1
```

Los Angeles midnight is 15:00 Beijing time in PDT and 16:00 in PST; the `la` slot fires at both and the guard picks the right one.
If the machine uses another time zone, run the `la` line hourly (`0 * * * *`) and the guard does the rest; for Beijing use
`CRON_TZ=Asia/Shanghai` where your cron supports it, or hourly with `--slot beijing`.
Do not commit a token. Put `GITHUB_TOKEN=...` at the top of the crontab, or leave it unset and rely on `gh auth login`.

### launchd (macOS, machine clock in Beijing time)

Two agents: `docs/launchd/com.jammyfu.ai-growth-atlas.beijing.plist` (00:00) and
`docs/launchd/com.jammyfu.ai-growth-atlas.la.plist` (15:00 and 16:00, guarded). Replace `/PATH/TO` with the clone path, then:

```bash
cp docs/launchd/com.jammyfu.ai-growth-atlas.*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jammyfu.ai-growth-atlas.beijing.plist
launchctl load ~/Library/LaunchAgents/com.jammyfu.ai-growth-atlas.la.plist
launchctl start com.jammyfu.ai-growth-atlas.la     # test: prints "skip: ..." unless it is LA midnight
```

They rely on `gh auth login` for the token (launchd has no shell profile).

## Verify

```bash
python3 tools/verify.py
```
