"""Pure helpers for GitHub Risers: star-history parsing, growth windows, ranking.

No network access and no third-party dependencies here, so everything is unit-testable.
All star numbers come from the GitHub REST API:
  GET /repos/{owner}/{repo}                      -> stargazers_count, created_at, ...
  GET /repos/{owner}/{repo}/stargazers/history   -> weekly buckets with daily counts
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Iterable

WINDOWS: dict[str, int] = {"week": 7, "month": 30, "year": 365}


def history_to_daily(pages: Iterable[list[dict[str, Any]]]) -> dict[dt.date, int]:
    """Flatten /stargazers/history pages into {date: stars_that_day}.

    Each entry is {"week": <epoch of week start>, "days": [7 ints, Sunday first], "total": n}.
    The day bucket date is week_start (UTC date) + index. GitHub documents that bucket
    boundaries are not guaranteed to align with UTC, so day-level numbers are approximate
    by up to one day at the window edges.
    """
    daily: dict[dt.date, int] = {}
    for page in pages:
        for entry in page:
            start = dt.datetime.fromtimestamp(int(entry["week"]), dt.timezone.utc).date()
            for i, n in enumerate(entry["days"]):
                day = start + dt.timedelta(days=i)
                daily[day] = daily.get(day, 0) + int(n)
    return daily


def window_gain(daily: dict[dt.date, int], today: dt.date, days: int) -> int:
    """Stars gained over the `days` complete UTC days before `today` (today itself excluded)."""
    first = today - dt.timedelta(days=days)
    return sum(n for d, n in daily.items() if first <= d < today)


def effective_days(created_at: str, today: dt.date, days: int) -> tuple[int, bool]:
    """Divisor for stars/day. For repos younger than the window, use the repo age.

    Returns (days_used, young) where young=True means the repo is younger than the window.
    """
    created = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
    age = max((today - created).days, 1)
    if age < days:
        return age, True
    return days, False


def compute_growth(
    daily: dict[dt.date, int], created_at: str, today: dt.date
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, days in WINDOWS.items():
        gained = window_gain(daily, today, days)
        used, young = effective_days(created_at, today, days)
        out[name] = {
            "window_days": days,
            "gained": gained,
            "effective_days": used,
            "per_day": round(gained / used, 3),
            "young": young,
        }
    return out


def snapshot_delta(
    snapshots: dict[str, int], today: dt.date, days: int, current: int
) -> dict[str, Any] | None:
    """Cross-check from our own daily snapshots: current - snapshot(today - days).

    Only returned when a snapshot dated exactly today-days exists. Net of un-stars.
    """
    key = (today - dt.timedelta(days=days)).isoformat()
    if key not in snapshots:
        return None
    return {"since": key, "delta": current - int(snapshots[key])}


def rank(projects: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Rank ok projects by growth window (per_day desc), or by total stars for key='total'."""
    ok = [p for p in projects if p.get("ok")]
    if key == "total":
        return sorted(ok, key=lambda p: (-p["stars"], p["name"]))
    return sorted(ok, key=lambda p: (-p["growth"][key]["per_day"], -p["stars"], p["name"]))


def star_history_svg(name: str) -> str:
    return f"https://api.star-history.com/svg?repos={name}&type=Date"


def star_history_page(name: str) -> str:
    return f"https://www.star-history.com/#{name}&Date"
