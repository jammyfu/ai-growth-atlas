"""'Hottest new repos in the last 7 days': discovery via the GitHub search API and ranking.

Everything comes from the API (search results + a fresh GET /repos/{r} for the top candidates).
Pure functions take an `api` callable (path -> parsed JSON) so they are unit-testable offline.

Criteria (also documented in docs/NEW_ARRIVALS.md):
  * created within the last WINDOW_DAYS (7) days (exact timestamp)
  * "AI repo" = carries one of AI_TOPICS, or AI_KEYWORDS appear in its name/description
  * not a fork, not archived, at least MIN_STARS stars
  * ranked by hotness = stars / max(age in days, 1)  (a new repo's stars are all gained since creation)
  * duplicates removed (see exclude_duplicates): tracked projects and anything shown in the other rankings
"""
from __future__ import annotations

import datetime as dt
import html
import re
import time
import urllib.parse
from typing import Any, Callable

WINDOW_DAYS = 7
MIN_STARS = 100
TOP_N = 20
REFRESH_TOP = 40  # candidates re-read via GET /repos/{r} before the final ranking
MAX_PAGES = 5     # search returns at most 100 per page
DESC_MAX = 160

AI_TOPICS = [
    "ai", "artificial-intelligence", "llm", "large-language-models", "llm-agent", "ai-agents",
    "ai-agent", "mcp", "mcp-server", "claude-code", "claude", "codex", "agent-skills",
    "generative-ai", "chatgpt", "openai", "anthropic", "gemini", "rag", "machine-learning",
    "deep-learning", "vibe-coding", "ai-coding", "cursor",
]
AI_KEYWORDS = ['"AI agent"', "LLM", '"Claude Code"', "Codex", '"MCP server"', '"agent skills"']

Api = Callable[[str], Any]


def since_iso(now: dt.datetime, days: int = WINDOW_DAYS) -> str:
    return (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_queries(now: dt.datetime) -> list[tuple[str, str]]:
    since = since_iso(now)
    base = f"created:>={since} stars:>={MIN_STARS} fork:false archived:false"
    qs = [(f"topic:{t}", f"topic:{t} {base}") for t in AI_TOPICS]
    qs += [(f"keyword:{k.strip(chr(34))}", f"{k} in:name,description {base}") for k in AI_KEYWORDS]
    return qs


def parse_ts(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def clean_description(text: str | None) -> str:
    """Untrusted API text -> one safe markdown table cell."""
    t = re.sub(r"\s+", " ", text or "").strip()
    t = html.escape(t, quote=False).replace("|", "/")
    return t if len(t) <= DESC_MAX else t[: DESC_MAX - 1].rstrip() + "…"


def search_all(api: Api, q: str, sleep: Callable[[float], None] = time.sleep) -> tuple[list[dict], int]:
    items: list[dict] = []
    total = 0
    for page in range(1, MAX_PAGES + 1):
        qs = urllib.parse.urlencode({"q": q, "sort": "stars", "order": "desc", "per_page": 100, "page": page})
        data = api(f"/search/repositories?{qs}")
        total = int(data.get("total_count", 0))
        got = data.get("items", [])
        items += got
        if len(got) < 100 or len(items) >= total:
            break
        sleep(2.2)
    return items, total


def to_item(repo: dict, now: dt.datetime) -> dict[str, Any]:
    created = parse_ts(repo["created_at"])
    age = max((now - created).total_seconds() / 86400, 1.0)
    stars = int(repo["stargazers_count"])
    return {
        "name": repo["full_name"],
        "repo_id": repo.get("id"),
        "url": repo["html_url"],
        "description": clean_description(repo.get("description")),
        "language": repo.get("language"),
        "stars": stars,
        "created_at": repo["created_at"],
        "age_days": round(age, 2),
        "per_day": round(stars / age, 1),
    }


def qualifies(repo: dict, now: dt.datetime) -> bool:
    created = parse_ts(repo["created_at"])
    return (not repo.get("fork") and not repo.get("archived") and not repo.get("private")
            and now - dt.timedelta(days=WINDOW_DAYS) <= created <= now
            and int(repo["stargazers_count"]) >= MIN_STARS)


def exclude_duplicates(items: list[dict], excluded_names: set[str]) -> tuple[list[dict], list[str]]:
    """Dedup rule. Returns (kept, dropped_names).

    1. Repos whose full name (case-insensitive) is in `excluded_names` are dropped: that set holds every
       tracked project and every repo shown in the week/month/year/total rankings, so the new-arrivals
       ranking never repeats a project from another ranking.
    2. The same repo found by several search queries is kept once (by repo id, else lower-cased name).
    """
    excluded = {n.lower() for n in excluded_names}
    seen: set[Any] = set()
    kept, dropped = [], []
    for it in items:
        key = it.get("repo_id") or it["name"].lower()
        if it["name"].lower() in excluded:
            dropped.append(it["name"])
            continue
        if key in seen:
            continue
        seen.add(key)
        kept.append(it)
    return kept, sorted(set(dropped))


def rank_items(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda i: (-i["per_day"], -i["stars"], i["name"].lower()))


def discover(api: Api, now: dt.datetime, excluded_names: set[str],
             sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Run all searches, refresh the best candidates, apply criteria and dedup, rank top N."""
    queries, found = [], {}
    for label, q in build_queries(now):
        entry: dict[str, Any] = {"label": label, "q": q}
        for attempt in (1, 2):  # one retry, e.g. after a secondary rate limit
            try:
                items, total = search_all(api, q, sleep)
                entry.update(ok=True, total=total)
                entry.pop("error", None)
                for r in items:
                    found.setdefault(r["full_name"].lower(), r)
                break
            except Exception as e:  # recorded, never hidden
                entry.update(ok=False, error=str(e)[:200])
                if attempt == 1:
                    sleep(15)
        queries.append(entry)
        sleep(2.2)  # search API: 30 requests/min
    result: dict[str, Any] = {
        "window_days": WINDOW_DAYS, "since": since_iso(now), "min_stars": MIN_STARS, "top_n": TOP_N,
        "queries": queries, "candidates_seen": len(found),
    }
    if not any(q["ok"] for q in queries):
        result.update(ok=False, error="every search query failed: " + queries[0].get("error", "?"), items=[])
        return result
    cands = [r for r in found.values() if qualifies(r, now)]
    cands.sort(key=lambda r: -int(r["stargazers_count"]))
    refreshed = []
    for r in cands[:REFRESH_TOP]:
        try:
            fresh = api(f"/repos/{r['full_name']}")
        except Exception:
            fresh = r  # search data is still API data; keep it
        if qualifies(fresh, now):
            refreshed.append(fresh)
    items, dropped = exclude_duplicates([to_item(r, now) for r in refreshed], excluded_names)
    result.update(ok=True, excluded_duplicates=dropped, items=rank_items(items)[:TOP_N])
    return result


def displayed_names(stats_projects: list[dict], top_n: int, rank: Callable[[list[dict], str], list[dict]]) -> set[str]:
    """Names shown in the week/month/year/total rankings (top N of each)."""
    names: set[str] = set()
    for key in ("week", "month", "year", "total"):
        names |= {p["name"] for p in rank(stats_projects, key)[:top_n]}
    return names


def overlap_with_rankings(newcomer_items: list[dict], stats_projects: list[dict], top_n: int,
                          rank: Callable[[list[dict], str], list[dict]]) -> set[str]:
    """Names that appear both in the new-arrivals list and in another ranking (must be empty)."""
    shown = {n.lower() for n in displayed_names(stats_projects, top_n, rank)}
    return {i["name"] for i in newcomer_items if i["name"].lower() in shown}
