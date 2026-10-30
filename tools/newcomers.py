"""Hottest new repos (last 7 days), per category: GitHub search API discovery + ranking.

Everything comes from the API (search + GET /repos/{r} for top candidates).
Pure functions take an `api` callable so they are unit-testable offline.

Category rules (topics / keywords / optional languages) live in data/categories.json
and are documented in docs/CATEGORIES.md and docs/NEW_ARRIVALS.md.
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
REFRESH_TOP = 30  # per category: candidates re-read via GET /repos/{r}
MAX_PAGES = 3     # search pages per query (rate-limit budget across categories)
DESC_MAX = 160

Api = Callable[[str], Any]


def since_iso(now: dt.datetime, days: int = WINDOW_DAYS) -> str:
    return (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_queries(now: dt.datetime, category: dict[str, Any]) -> list[tuple[str, str]]:
    """Build search queries from one category's topics, keywords and languages."""
    since = since_iso(now)
    base = f"created:>={since} stars:>={MIN_STARS} fork:false archived:false"
    qs: list[tuple[str, str]] = []
    for t in category.get("topics") or []:
        qs.append((f"topic:{t}", f"topic:{t} {base}"))
    for k in category.get("keywords") or []:
        label = k.strip('"')
        qs.append((f"keyword:{label}", f"{k} in:name,description {base}"))
    for lang in category.get("languages") or []:
        qs.append((f"language:{lang}", f"language:{lang} {base}"))
    return qs


def parse_ts(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def clean_description(text: str | None) -> str:
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
    """Drop names in excluded_names (case-insensitive); collapse multi-query hits by repo id."""
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


def discover_category(api: Api, now: dt.datetime, category: dict[str, Any],
                      excluded_names: set[str],
                      sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Run searches for one category, refresh candidates, dedup, rank top N."""
    queries, found = [], {}
    for label, q in build_queries(now, category):
        entry: dict[str, Any] = {"label": label, "q": q}
        for attempt in (1, 2):
            try:
                items, total = search_all(api, q, sleep)
                entry.update(ok=True, total=total)
                entry.pop("error", None)
                for r in items:
                    found.setdefault(r["full_name"].lower(), r)
                break
            except Exception as e:
                entry.update(ok=False, error=str(e)[:200])
                if attempt == 1:
                    sleep(15)
        queries.append(entry)
        sleep(2.2)
    result: dict[str, Any] = {
        "category": category["id"],
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
            fresh = r
        if qualifies(fresh, now):
            refreshed.append(fresh)
    items, dropped = exclude_duplicates([to_item(r, now) for r in refreshed], excluded_names)
    result.update(ok=True, excluded_duplicates=dropped, items=rank_items(items)[:TOP_N])
    return result


def discover_all(api: Api, now: dt.datetime, categories: list[dict[str, Any]],
                 projects_meta: list[dict[str, Any]], stats_projects: list[dict],
                 rank: Callable[[list[dict], str], list[dict]],
                 sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Discover newcomers for every category (AI first). Exclusive across categories by order.

    Within a category, newcomers never repeat that category's tracked projects or its
    week/month/year/total top N. A repo already shown in an earlier category's newcomers
    is also excluded (AI is primary, so it claims first).
    """
    by_cat: dict[str, dict[str, Any]] = {}
    claimed: set[str] = set()  # lower-cased names already shown in an earlier category
    ordered = sorted(categories, key=lambda c: (0 if c.get("primary") else 1, c.get("order", 99), c["id"]))
    for cat in ordered:
        cid = cat["id"]
        tracked = {p["name"] for p in projects_meta if p.get("category") == cid}
        cat_stats = [p for p in stats_projects if p.get("name") in tracked]
        excluded = tracked | displayed_names(cat_stats, TOP_N, rank) | claimed
        result = discover_category(api, now, cat, excluded, sleep)
        by_cat[cid] = result
        if result.get("ok"):
            claimed |= {i["name"].lower() for i in result.get("items", [])}
    ok_any = any(r.get("ok") for r in by_cat.values())
    return {
        "ok": ok_any,
        "window_days": WINDOW_DAYS,
        "since": since_iso(now),
        "min_stars": MIN_STARS,
        "top_n": TOP_N,
        "categories": by_cat,
        "error": None if ok_any else "every category search failed",
    }


# Back-compat helpers used by tests / older call sites
def build_queries_ai(now: dt.datetime, categories: list[dict[str, Any]] | None = None) -> list[tuple[str, str]]:
    if categories:
        ai = next((c for c in categories if c["id"] == "ai"), categories[0])
        return build_queries(now, ai)
    return []


def discover(api: Api, now: dt.datetime, excluded_names: set[str],
             sleep: Callable[[float], None] = time.sleep,
             category: dict[str, Any] | None = None) -> dict[str, Any]:
    """Discover for a single category (defaults to a minimal AI topic set for unit tests)."""
    cat = category or {
        "id": "ai",
        "topics": ["ai", "llm", "mcp"],
        "keywords": ["LLM"],
        "languages": [],
    }
    return discover_category(api, now, cat, excluded_names, sleep)


def displayed_names(stats_projects: list[dict], top_n: int, rank: Callable[[list[dict], str], list[dict]]) -> set[str]:
    names: set[str] = set()
    for key in ("week", "month", "year", "total"):
        names |= {p["name"] for p in rank(stats_projects, key)[:top_n]}
    return names


def overlap_with_rankings(newcomer_items: list[dict], stats_projects: list[dict], top_n: int,
                          rank: Callable[[list[dict], str], list[dict]]) -> set[str]:
    shown = {n.lower() for n in displayed_names(stats_projects, top_n, rank)}
    return {i["name"] for i in newcomer_items if i["name"].lower() in shown}


def projects_in_category(stats_projects: list[dict], projects_meta: list[dict], category_id: str) -> list[dict]:
    names = {p["name"] for p in projects_meta if p.get("category") == category_id}
    return [p for p in stats_projects if p.get("name") in names]
