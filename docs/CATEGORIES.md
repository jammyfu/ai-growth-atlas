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
2. **New arrivals (7 days)**: discovered with the GitHub search API, **by topic only**. For each category the query pool is one `topic:<t>` search per topic listed in `data/categories.json`, with the shared filters
   `created:>=now-7d stars:>=100 fork:false archived:false`.
   - **A repo must carry at least one of the category's topics itself** (`has_category_topic` in `tools/newcomers.py`). Keyword and language searches were removed: words like "design" or "security" in a description, or a bare `language:TypeScript`, pulled in unrelated and star-farmed repos.
   - Generic topics (`design`, `security`, `web`, `data`, `ui`, `javascript`, `typescript`, `creative`, `icon`, `canvas`, `graphics`, `cloud`, `networking`, `editor`, `terminal`, `analytics`, `streaming`) are not used; a test fails if one comes back.
3. **Cross-category exclusivity for newcomers**: categories run in the order above (AI first). A repo already shown in an earlier category's newcomers board is dropped from later ones, so the same new repo is not listed twice.
4. **Within a category**: newcomers never repeat that category's tracked projects or its week / month / year / total top 20 (case-insensitive). See [NEW_ARRIVALS.md](NEW_ARRIVALS.md).

Topics are tags set by the repo owner. They are not a manual editorial review, so an occasional off-topic hit is possible and is accepted.

## Suspected cracked / pirated / activator repos

Star-farmed repos named after commercial software ("Canva-Pro", "Adobe-Acrobat-Pro", "KMS-Pico") with canned
descriptions ("full working installer", "pre-activated") are **kept in the new-repo boards but flagged and ranked
last**:

- They get `suspicious: "<reason>"` in `stats.json` and a `⚠` after the name; a note under the table explains it.
- Within a board they are always **after every normal repo**, however many stars per day they have
  (`newcomers.rank_items`).
- They are **never a category leader**: the "Category leaders this round" table in the READMEs skips them
  (`render_readme.leaders`), showing n/a when only suspected repos are left.
- Candidates are refreshed normal-first, so a flood of such repos cannot push normal repos out of the top-N budget.

Rules (`tools/spam.py`, `suspicious_reason`), matched on repo name, description and topics:

1. Phrases: crack / cracked, keygen, activator, pre-activated, KMS-Pico, free download, full version, serial/license/product key, warez, nulled, repack, mod apk, all features unlocked, standalone setup, full working installer, ready-to-run desktop, ...
2. "<anything> 2026 ... installer / setup / edition / desktop" copy.
3. A description that is only `Published: <date>`.
4. A commercial software name in the repo name (Adobe, Photoshop, Canva, Autodesk, AutoCAD, Cinema 4D, Microsoft Office, Wondershare, ...) unless the owner is the vendor.
5. A `-Pro` / `-Premium` / year-suffixed name with no description and no language.

This is a heuristic, not a verdict: a flagged repo is only moved down, never hidden. `tests/test_spam.py` pins the rules, the ordering, the leader exclusion and that the scheduled entry points use the same code.

## Per-category boards

Every category has, in this order:

1. Hottest new repos (created in the last 7 days)
2. Fastest rising this week (last 7 days)
3. Fastest rising this month (last 30 days)
4. Fastest rising this year (last 365 days)
5. Total stars (all time) — always last

Each board shows up to the top 20. Star numbers always come from the GitHub API; missing data is marked missing, never estimated.
