# Hottest new repos (created in the last 7 days)

The first board inside every category. Everything comes from the GitHub API; nothing is estimated or hand-picked.
It is rebuilt on every run (Beijing 00:00 and Los Angeles 00:00), stored in the slot folder
`rankings/<date>/<slot>/` and copied to `latest/` like the other rankings. Code: `tools/newcomers.py`.
Category rules: [CATEGORIES.md](CATEGORIES.md).

## How candidates are found

For each category in `data/categories.json`, the updater runs:

`GET /search/repositories?q=<query>&sort=stars&order=desc&per_page=100` (paged up to 3 pages), one query per
topic, keyword and optional language, all with the same filters:

```
created:>=<now minus 7 days> stars:>=100 fork:false archived:false
```

Topics / keywords / languages are those listed on the category. "Belongs to the category" therefore means
"tagged or described that way by its owner"; there is no manual curation beyond the topic/keyword lists.

## Criteria

1. Created within the last 7 days (exact timestamp check on `created_at`).
2. At least 100 stars, not a fork, not archived, not private.
3. The best 30 candidates by search star count (per category) are re-read with `GET /repos/{owner}/{repo}`.
4. **Hotness = stars ÷ max(age in days, 1).**
5. Ranked by hotness (ties: more stars, then name), top 20 shown per category.

If every search query for a category fails, that category's new-repo board is shown as missing. If only some
queries fail, the README says so. Search is index-based and can lag by minutes.

## Deduplication rule

No project may appear in two boards **of the same category**, and a newcomer is not repeated across categories:

1. Within a category, a repo is dropped from newcomers if its full name (case-insensitive) is a **tracked project
   in that category** or appears in that category's **top 20 of week, month, year or total** in the same run.
   Dropped names are recorded under `newcomers.categories.<id>.excluded_duplicates`.
2. Across categories, discovery runs AI first, then the others in order. Names already shown in an earlier
   category's newcomers board are excluded from later ones.
3. The same repo found by several queries inside one category is kept once (by repo id).

`tests/test_newcomers.py` enforces the within-category rule on committed data and on every history snapshot
that uses the multi-category shape (`overlap_with_rankings` must be empty), plus unit tests for
case-insensitivity and multi-query duplicates.

A new repo is not added to `data/projects.json` automatically.

## Descriptions

The table shows the repo's own GitHub description (made safe for a table cell). A hand-written translation in
`data/newcomer_i18n.json` is shown on a page of that language while its `src` matches; otherwise the original.
Gaps: `python3 tools/newcomer_i18n.py`.
