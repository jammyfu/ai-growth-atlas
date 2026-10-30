"""Per-slot ranking snapshots, latest/ copy and the history index.

Layout (all generated; snapshots are written once per slot-run and kept forever):
  rankings/<date>/<slot-id>/stats.json     full API-derived data of that run + "slot" metadata
  rankings/<date>/<slot-id>/rankings.md    top-20 tables (English, compact) for that run
  rankings/README.md                       history index linking every snapshot, newest first
  latest/stats.json, latest/rankings.md    copy of the newest run

Slots: cn = Beijing 00:00 (folder date = Asia/Shanghai date), pt = Los Angeles 00:00
(folder date = America/Los_Angeles date), manual = any other run (folder date and time = UTC).
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import atlas_core as core

TOP_N = 20
SLOTS = {
    "cn": ("Asia/Shanghai", "Beijing 00:00"),
    "pt": ("America/Los_Angeles", "Los Angeles 00:00"),
}
SLOT_CHOICES = ("auto", "cn", "pt", "manual")


def detect_slot(now_utc: dt.datetime) -> str:
    """cn if it is 00:xx in Beijing, pt if 00:xx in Los Angeles, otherwise manual."""
    for name, (tz, _label) in SLOTS.items():
        if now_utc.astimezone(ZoneInfo(tz)).hour == 0:
            return name
    return "manual"


def make_slot(now_utc: dt.datetime, requested: str = "auto") -> dict[str, str]:
    if requested not in SLOT_CHOICES:
        raise ValueError(f"slot must be one of {SLOT_CHOICES}")
    name = detect_slot(now_utc) if requested == "auto" else requested
    if name in SLOTS:
        tz, label = SLOTS[name]
        local = now_utc.astimezone(ZoneInfo(tz))
        return {"name": name, "id": f"{name}-0000", "date": local.date().isoformat(),
                "label": label, "tz": tz}
    utc = now_utc.astimezone(dt.timezone.utc)
    return {"name": "manual", "id": f"manual-{utc:%H%M}", "date": utc.date().isoformat(),
            "label": f"Manual {utc:%H:%M} UTC", "tz": "UTC"}


def _rows(ranked: list[dict], key: str) -> list[str]:
    out = []
    for i, p in enumerate(ranked, 1):
        if key == "total":
            out.append(f"| {i} | [{p['name']}](https://github.com/{p['name']}) | {p['stars']:,} |")
            continue
        g = p["growth"][key]
        mark = f" † (÷{g['effective_days']}d)" if g["young"] else ""
        out.append(f"| {i} | [{p['name']}](https://github.com/{p['name']}) | +{g['gained']:,} | "
                   f"{g['per_day']:,.1f}{mark} | {p['stars']:,} |")
    return out


def _new_rows(items: list[dict]) -> list[str]:
    return [f"| {i} | [{it['name']}]({it['url']}) | {it['created_at'][:10]} | {it['stars']:,} | "
            f"{it['per_day']:,.1f} |" for i, it in enumerate(items, 1)]


def render_rankings_md(stats: dict[str, Any]) -> str:
    from i18n import S
    s = S["en"]
    slot = stats.get("slot") or {"label": "unlabelled", "date": stats["today_utc"], "id": "n/a"}
    lines = [
        f"# Rankings snapshot: {slot['label']}, {slot['date']}", "",
        f"Slot `{slot['id']}`. Data fetched from the GitHub API at {stats['generated_at']} "
        f"(window end: {stats['today_utc']} UTC). Top {TOP_N}.", "",
    ]
    projects = stats["projects"]
    new = stats.get("newcomers")
    if new is not None:  # snapshots written before this ranking existed have no such key
        lines += [f"## {s['new']}", ""]
        if not new["ok"]:
            lines += [s["new_failed"].format(error=new["error"]), ""]
        else:
            lines += ["| # | Repo | Created (UTC) | Stars | Stars/day |", "|---|---|---|---:|---:|"]
            lines += _new_rows(new["items"][:TOP_N]) + [""]
            bad = [q for q in new["queries"] if not q["ok"]]
            if bad:
                lines += [s["new_partial"].format(failed=len(bad), total=len(new["queries"])), ""]
    for key in ("week", "month", "year"):
        lines += [f"## {s[key]}", "",
                  "| # | Project | Stars gained | Stars/day | Total stars |", "|---|---|---:|---:|---:|"]
        lines += _rows(core.rank(projects, key)[:TOP_N], key) + [""]
    lines += [f"## {s['total']}", "", "| # | Project | Total stars |", "|---|---|---:|"]
    lines += _rows(core.rank(projects, "total")[:TOP_N], "total") + [""]
    missing = [p for p in projects if not p.get("ok")]
    lines += [f"## {s['missing_title']}", ""]
    lines += [f"- `{p['name']}`: {p['error']}" for p in missing] if missing else [s["missing_none"]]
    lines += ["", "† The repo is younger than the window; stars/day is divided by the repo age in days.", ""]
    return "\n".join(lines)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")


def write_snapshot(root: Path, stats: dict[str, Any]) -> Path:
    slot = stats["slot"]
    d = root / "rankings" / slot["date"] / slot["id"]
    write_json(d / "stats.json", stats)
    (d / "rankings.md").write_text(render_rankings_md(stats), "utf-8")
    return d


def scan_snapshots(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    found = []
    for f in sorted((root / "rankings").glob("*/*/stats.json")):
        found.append((f.parent, json.loads(f.read_text("utf-8"))))
    found.sort(key=lambda t: t[1]["generated_at"], reverse=True)
    return found


def render_index(root: Path) -> str:
    snaps = scan_snapshots(root)
    lines = [
        "# Ranking history", "",
        "Every update stores its full result in its own folder, `rankings/<date>/<slot>/`, and the history is kept. "
        "Slots: `cn-0000` = Beijing 00:00, `pt-0000` = Los Angeles 00:00, `manual-HHMM` = any other run (UTC). "
        "Folder dates are the local date of the slot's time zone.", "",
        "Latest: [`latest/rankings.md`](../latest/rankings.md) · [`latest/stats.json`](../latest/stats.json) · "
        "[README](../README.md)", "",
        "| Date | Slot | Fetched (UTC) | #1 new (7 days) | #1 this week | #1 this month | #1 this year | Snapshot |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d, st in snaps:
        slot = st["slot"]
        tops = []
        for key in ("week", "month", "year"):
            r = core.rank(st["projects"], key)
            tops.append(f"{r[0]['name']} ({r[0]['growth'][key]['per_day']:,.0f}/day)" if r else "n/a")
        new = st.get("newcomers")
        top_new = (f"{new['items'][0]['name']} ({new['items'][0]['per_day']:,.0f}/day)"
                   if new and new.get("ok") and new["items"] else "n/a")
        rel = d.relative_to(root / "rankings").as_posix()
        lines.append(f"| {slot['date']} | {slot['label']} (`{slot['id']}`) | {st['generated_at']} | "
                     f"{top_new} | {tops[0]} | {tops[1]} | {tops[2]} | [{rel}]({rel}/rankings.md) · [json]({rel}/stats.json) |")
    if not snaps:
        lines.append("| | | | | | | | no snapshots yet |")
    lines.append("")
    return "\n".join(lines)


def render_latest_and_index(root: Path) -> dict[Path, str]:
    """Return {path: expected text} for latest/ and the index, derived from the newest snapshot."""
    out: dict[Path, str] = {root / "rankings/README.md": render_index(root)}
    snaps = scan_snapshots(root)
    if snaps:
        newest = snaps[0][1]
        out[root / "latest/stats.json"] = json.dumps(newest, ensure_ascii=False, indent=2) + "\n"
        out[root / "latest/rankings.md"] = render_rankings_md(newest)
    return out


def refresh_latest_and_index(root: Path) -> None:
    for path, text in render_latest_and_index(root).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, "utf-8")


def stale_latest_and_index(root: Path) -> list[str]:
    return [str(p.relative_to(root)) for p, t in render_latest_and_index(root).items()
            if not p.exists() or p.read_text("utf-8") != t]
