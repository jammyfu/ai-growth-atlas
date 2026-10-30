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

## 2026-10-30

### Two LA crons plus a time-zone guard

- GitHub cron is UTC-only and LA midnight moves between 07:00 and 08:00 UTC with DST, so both are scheduled and `tools/schedule_guard.py` lets exactly one pass.

### Top 20 per ranking, 20+ tracked projects

- New projects follow the existing topic line (fast-rising AI agent / coding-agent related repos), chosen by measured 7-day growth from the API, not by total stars.

### History snapshots are real runs only

- A snapshot folder is written only by an actual run at that slot. Past slots are not back-filled, because the star count at that moment cannot be recovered from the API.

### New arrivals: hotness and dedup

- Hotness = stars / max(age days, 1); descriptions are the repo's own GitHub text (not translated).
- Dedup excludes tracked projects and all displayed top-20 repos, so no project is in two rankings; a repo must be added to `data/projects.json` by the owner to be tracked.

## 2026-10-30 (categories)

### Newcomers are found by topic only

- Keyword and language searches pulled in unrelated and star-farmed repos. A repo must carry one of the category's topics; generic topics are not used.

### Suspected cracked / pirated repos: keep, flag, rank last

- Owner decision: do not exclude them. They are marked ⚠, always rank after every normal repo and never lead a category or the leaders table. Rules in `tools/spam.py`, documented in `docs/CATEGORIES.md`.

### One code path for every scheduled run

- Beijing cron, both Los Angeles crons, `workflow_dispatch` and the local launchd jobs all end in `tools/update_stars.py --slot <slot>`, so the rules above apply to every run.

## 2026-10-30 (CoderSkills harness)

### Follow `continuous-project-loop` and `multi-project-program-management`; other CoderSkills skills do not apply

- Applied: standard file set, one plan entry, record order, verify hardening rule, dirty-worktree rule written into repo files, planning rules (one Goal, 3-7 tasks, Out of Scope, Next Candidates).
- Not adopted: `sync_or_queue.py` / LaunchAgent safe-sync tooling (this repo changes through pull requests; the only automated writer is the daily job), `docs/architecture/*ROADMAP*.md` (not a platform-core project), `git-autosync-signal` (supports only `dramaforge` and `clippipeline`).
- `readme-tech-visualizer`: audit only. The README stays the slim first screen; the header image belongs to the GEO work, so no hero or tech-badge block is generated.
