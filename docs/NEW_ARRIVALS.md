# Hottest new repos (created in the last 7 days)

The first ranking in every README. Everything comes from the GitHub API; nothing is estimated or hand-picked.
It is rebuilt on every run (Beijing 00:00 and Los Angeles 00:00), stored in the slot folder
`rankings/<date>/<slot>/` and copied to `latest/` like the other rankings. Code: `tools/newcomers.py`.

## How candidates are found

`GET /search/repositories?q=<query>&sort=stars&order=desc&per_page=100` (paged up to 5 pages), one query per
topic and per keyword, all with the same filters:

```
created:>=<now minus 7 days> stars:>=100 fork:false archived:false
```

- **Topics** (a repo carrying any of them counts as an AI repo):
  `ai`, `artificial-intelligence`, `llm`, `large-language-models`, `llm-agent`, `ai-agents`, `ai-agent`, `mcp`,
  `mcp-server`, `claude-code`, `claude`, `codex`, `agent-skills`, `generative-ai`, `chatgpt`, `openai`,
  `anthropic`, `gemini`, `rag`, `machine-learning`, `deep-learning`, `vibe-coding`, `ai-coding`, `cursor`
- **Keywords** in the repo name or description: `"AI agent"`, `LLM`, `"Claude Code"`, `Codex`, `"MCP server"`, `"agent skills"`

"AI repo" therefore means "tagged or described as AI by its owner"; there is no manual curation, so an
occasional off-topic repo that uses these tags can appear.

## Criteria

1. Created within the last 7 days (exact timestamp check on `created_at`, not just the date).
2. At least 100 stars, not a fork, not archived, not private.
3. The best 40 candidates by search star count are re-read with `GET /repos/{owner}/{repo}` so the star count is fresh.
4. **Hotness = stars ÷ max(age in days, 1).** A repo under 7 days old has gained all its stars since creation, so
   this is its average stars/day; the 1-day floor stops a repo created minutes ago from ranking on noise.
5. Ranked by hotness (ties: more stars, then name), top 20 shown.

If every search query fails, the ranking is shown as missing with the error. If only some queries fail, the
README says so (the candidate pool may be incomplete). Search is index-based and can lag by minutes.

## Deduplication rule

No project may appear in two rankings:

1. A repo is dropped from this ranking if its full name (case-insensitive) is a **tracked project**
   (`data/projects.json`) or appears in the **top 20 of the week, month, year or total-stars ranking** of the same run.
   The dropped names are recorded in `stats.json` under `newcomers.excluded_duplicates`.
2. The same repo found by several queries is kept once (by repo id).

The week/month/year/total rankings only contain tracked projects, so rule 1 is a superset check on purpose.
`tests/test_newcomers.py` enforces it on the committed data and on every history snapshot
(`overlap_with_rankings` must be empty), plus unit tests for case-insensitivity and multi-query duplicates.

A new repo is not added to `data/projects.json` automatically. To track it permanently, add it there (with
five-language `desc`); from then on it leaves this ranking and competes in the others.

## Descriptions

The table shows the repo's own GitHub description in its original language (made safe for a table cell:
newlines removed, `|` replaced, HTML escaped, cut at 160 characters). It is never rewritten by the generator.
A hand-written translation in `data/newcomer_i18n.json` is shown instead on a page of that language, but only while its
`src` equals the current description; a repo without a (current) translation shows the original. Gaps:
`python3 tools/newcomer_i18n.py`.
