#!/usr/bin/env python3
"""Fetch real star data from the GitHub API and write data/stats.json + data/stars.json.

Usage:
  GITHUB_TOKEN=... python tools/update_stars.py [--today YYYY-MM-DD] [--no-render]

Only the Python standard library is used. No telemetry: the only network calls go to
api.github.com. A repo whose data cannot be fetched is recorded as {"ok": false, "error": ...}
and shown as "missing" in the README; nothing is estimated.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive  # noqa: E402
import atlas_core as core  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
PER_PAGE = 30  # documented maximum for /stargazers/history
MAX_PAGES = 100  # documented maximum page
YEAR_DAYS = core.WINDOWS["year"]


class GitHubError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


def api_get(path: str, token: str, retries: int = 3) -> Any:
    req = urllib.request.Request(
        API + path,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-growth-atlas-updater",
        },
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            if e.code in (500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise GitHubError(e.code, body) from None
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise GitHubError(0, str(e.reason)) from None
    raise GitHubError(0, "unreachable")


def fetch_history_pages(name: str, token: str, today: dt.date) -> tuple[list[list[dict]], bool]:
    """Fetch newest-first history pages until the one-year window is covered.

    Returns (pages, complete) where complete=True means the repo's whole history was read.
    """
    pages: list[list[dict]] = []
    need_after = today - dt.timedelta(days=YEAR_DAYS + 7)
    for page in range(1, MAX_PAGES + 1):
        data = api_get(f"/repos/{name}/stargazers/history?per_page={PER_PAGE}&page={page}", token)
        if not data:
            return pages, True
        pages.append(data)
        oldest = dt.datetime.fromtimestamp(int(data[-1]["week"]), dt.timezone.utc).date()
        if len(data) < PER_PAGE:
            return pages, True
        if oldest <= need_after:
            return pages, False
    return pages, False


def fetch_project(name: str, token: str, today: dt.date, snaps: dict[str, int]) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": name}
    try:
        meta = api_get(f"/repos/{name}", token)
        pages, complete = fetch_history_pages(name, token, today)
    except GitHubError as e:
        entry.update(ok=False, error=str(e))
        return entry
    daily = core.history_to_daily(pages)
    stars = int(meta["stargazers_count"])
    entry.update(
        ok=True,
        stars=stars,
        created_at=meta["created_at"],
        archived=bool(meta.get("archived")),
        github_description=meta.get("description"),
        growth=core.compute_growth(daily, meta["created_at"], today),
        history_complete=complete,
        history_total=sum(daily.values()) if complete else None,
        snapshot_check={
            k: core.snapshot_delta(snaps, today, d, stars) for k, d in core.WINDOWS.items()
        },
    )
    return entry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today", help="override UTC date (YYYY-MM-DD), for tests/back-fills")
    ap.add_argument("--slot", choices=archive.SLOT_CHOICES, default="auto",
                    help="cn = Beijing 00:00, pt = Los Angeles 00:00, manual, or auto-detect from the clock")
    ap.add_argument("--now", default=os.environ.get("ATLAS_NOW_UTC"),
                    help="override the current time (ISO 8601 UTC), for tests/back-fills")
    ap.add_argument("--no-render", action="store_true", help="skip README generation")
    args = ap.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("error: set GITHUB_TOKEN (e.g. GITHUB_TOKEN=$(gh auth token))", file=sys.stderr)
        return 2

    now = (dt.datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
           if args.now else dt.datetime.now(dt.timezone.utc))
    today = dt.date.fromisoformat(args.today) if args.today else now.date()
    projects = json.loads((ROOT / "data/projects.json").read_text("utf-8"))
    snap_path = ROOT / "data/stars.json"
    snapshots: dict[str, dict[str, int]] = json.loads(snap_path.read_text("utf-8"))
    snapshots = {k: v for k, v in snapshots.items() if not k.startswith("_") and k != "example"}

    results = []
    for p in projects:
        name = p["name"]
        r = fetch_project(name, token, today, snapshots.get(name, {}))
        results.append(r)
        if r["ok"]:
            g = r["growth"]
            print(f"ok   {name:36s} stars={r['stars']:>8} 7d={g['week']['gained']:>7} "
                  f"30d={g['month']['gained']:>7} 365d={g['year']['gained']:>7}")
            snapshots.setdefault(name, {})[today.isoformat()] = r["stars"]
        else:
            print(f"MISS {name:36s} {r['error']}", file=sys.stderr)

    if not any(r["ok"] for r in results):
        print("error: no project could be fetched; files left untouched", file=sys.stderr)
        return 1

    stats = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today_utc": today.isoformat(),
        "slot": archive.make_slot(now, args.slot),
        "windows_days": core.WINDOWS,
        "method": (
            "stars = GET /repos/{r}.stargazers_count; gained = sum of daily buckets from "
            "GET /repos/{r}/stargazers/history over the N complete UTC days before today"
        ),
        "projects": results,
    }
    (ROOT / "data/stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", "utf-8")
    header = {
        "_comment": "Daily snapshots of stargazers_count from the GitHub API. "
                    "Format: { \"owner/repo\": { \"YYYY-MM-DD\": stars } }. Appended by tools/update_stars.py."
    }
    snap_path.write_text(
        json.dumps({**header, **{k: dict(sorted(v.items())) for k, v in sorted(snapshots.items())}},
                   ensure_ascii=False, indent=2) + "\n", "utf-8")

    snap_dir = archive.write_snapshot(ROOT, stats)
    archive.refresh_latest_and_index(ROOT)
    print(f"snapshot: {snap_dir.relative_to(ROOT)}  (latest/ and rankings/README.md refreshed)")

    if not args.no_render:
        import render_readme
        render_readme.main([])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
