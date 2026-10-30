# GitHub Risers: facts

A one-page, quotable summary. Details live in [CATEGORIES.md](CATEGORIES.md), [NEW_ARRIVALS.md](NEW_ARRIVALS.md) and [DAILY_UPDATE.md](DAILY_UPDATE.md). Nothing here is estimated; if a number is not in the repo's data files, it is not stated here.

| Item | Fact |
|---|---|
| Name | GitHub Risers (formerly `ai-growth-atlas`; Chinese: GitHub 涨星榜) |
| What it is | A leaderboard of GitHub repositories ranked by **star growth** (stars gained per day), not by total stars |
| What it is not | Not an official GitHub product, not affiliated with GitHub, not a manually curated list, not a star-buying or promotion service |
| Main board | AI (LLMs, agents, MCP, coding copilots, generative AI) |
| Other boards | Developer Tools, Security, Web / Frontend, Infrastructure, Design / Creative, Data |
| Boards per category | 1. Hottest new repos (created in the last 7 days) 2. Fastest rising this week 3. This month 4. This year 5. Total stars (always last). Up to the top 20 each |
| Growth windows | 7, 30 and 365 complete UTC days before the run day |
| Growth formula | `per_day = stars gained in the window / days used`. A repo younger than the window uses its own age as the divisor and is marked young |
| New-repo hotness | `stars / max(age in days, 1)`, repos created in the last 7 days, at least 100 stars, not a fork, not archived |
| Star data source | GitHub REST API only: `GET /repos/{owner}/{repo}` for the total and `GET /repos/{owner}/{repo}/stargazers/history` for daily gains. Missing data is shown as missing, never filled in |
| New-repo discovery | GitHub search API, one `topic:<t>` query per category topic; the repo must carry a category topic itself |
| Update schedule | Twice a day: 00:00 Beijing time (UTC+8) and 00:00 Los Angeles time (follows daylight saving). Runs by GitHub Actions cron, so a run can start a few minutes late |
| History | Every run is kept under `rankings/<date>/<slot>/`; the newest copy is in `latest/` |
| Languages | English, 简体中文, 繁體中文, 日本語, 한국어 |
| Suspected cracked / pirated repos | Flagged by a published heuristic (`tools/spam.py`) and ranked after all normal repos in the new-repo board; never a category leader; never hidden |
| Fake stars | Not detected. Star counts are whatever the GitHub API returns |
| Use of AI | Rankings are computed by plain scripts. Translations and polish of repo descriptions can be produced with an AI model in an optional CI step; numbers never are |
| Telemetry | None. No analytics, tracking or beacon scripts |
| License | MIT |
| Author | [jammyfu](https://github.com/jammyfu) |
| Repository | <https://github.com/jammyfu/github-risers> |
| Website | <https://jammyfu.github.io/github-risers/> |
| Cite | See [CITATION.cff](../CITATION.cff) |
