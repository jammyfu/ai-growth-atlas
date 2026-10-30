# Categories

GitHub Risers ranks open-source repositories **by category**. AI is the primary (default top) category; the others cover common areas of GitHub.

Defined in [`data/categories.json`](../data/categories.json). Code that searches and ranks reads that file; this doc is the human-readable rule set.

## Category list (order)

| id | English | Role |
|---|---|---|
| `ai` | AI | **Primary** — shown first in every README |
| `devtools` | Developer Tools | CLIs, editors, package managers, linters, build tools |
| `security` | Security | Scanners, SAST, supply-chain and runtime security |
| `web` | Web / Frontend | Frontend frameworks, UI kits, CSS, browser tooling |
| `infra` | Infrastructure | Containers, Kubernetes, cloud, networking, observability |
| `data` | Data | Databases, analytics, ETL, data engineering |
| `design` | Design / Creative | Design systems, drawing, animation, creative tooling |

## How a repo is classified

1. **Tracked projects** (`data/projects.json`): each entry has exactly one `category` id. Growth rankings (week / month / year / total) inside a category only include that category's tracked projects.
2. **New arrivals (7 days)**: discovered with the GitHub search API. For each category the query pool is:
   - `topic:<t>` for every topic in the category
   - `<keyword> in:name,description` for every keyword
   - optional `language:<lang>` when listed
   - shared filters: `created:>=now-7d stars:>=100 fork:false archived:false`
3. **Cross-category exclusivity for newcomers**: categories run in the order above (AI first). A repo already shown in an earlier category's newcomers board is dropped from later ones, so the same new repo is not listed twice.
4. **Within a category**: newcomers never repeat that category's tracked projects or its week / month / year / total top 20 (case-insensitive). See [NEW_ARRIVALS.md](NEW_ARRIVALS.md).

Topics and keywords are signals from the repo owner (tags and description text). They are not a manual editorial review, so an occasional off-topic hit is possible and is accepted.

## Per-category boards

Every category has, in this order:

1. Hottest new repos (created in the last 7 days)
2. Fastest rising this week (last 7 days)
3. Fastest rising this month (last 30 days)
4. Fastest rising this year (last 365 days)
5. Total stars (all time) — always last

Each board shows up to the top 20. Star numbers always come from the GitHub API; missing data is marked missing, never estimated.
