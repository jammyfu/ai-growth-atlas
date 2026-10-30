"""Per-slot ranking snapshots, latest/ copy and the history index.

Layout (all generated; snapshots are written once per slot-run and kept forever):
  rankings/<date>/<slot-id>/stats.json     full API-derived data of that run + "slot" metadata
  rankings/<date>/<slot-id>/rankings.md    top-20 tables (English, compact) for that run
  rankings/README.md                       history index linking every snapshot, newest first
  latest/stats.json, latest/rankings.md    copy of the newest run

Every page except stats.json also exists once per language, named like the READMEs:
rankings.<lang>.md, README.<lang>.md (rankings/), latest/rankings.<lang>.md, for every code in
i18n.LANGS other than "en". The strings come from i18n.S; the data is the same stats.json.

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
from i18n import LANGS, S

TOP_N = 20
SLOTS = {
    "cn": ("Asia/Shanghai", "Beijing 00:00"),
    "pt": ("America/Los_Angeles", "Los Angeles 00:00"),
}
SLOT_CHOICES = ("auto", "cn", "pt", "manual")


def rankings_name(lang: str) -> str:
    """File name of the rankings page: rankings.md for English, rankings.<lang>.md otherwise."""
    return "rankings.md" if lang == "en" else f"rankings.{lang}.md"


def index_name(lang: str) -> str:
    """File name of the history index in rankings/: README.md or README.<lang>.md."""
    return "README.md" if lang == "en" else f"README.{lang}.md"


def slot_label(slot: dict[str, str], lang: str) -> str:
    """The slot's label in `lang`; unknown slots keep the label stored in stats.json."""
    s = S[lang]
    if slot.get("name") == "cn":
        return s["slot_cn"]
    if slot.get("name") == "pt":
        return s["slot_pt"]
    sid = slot.get("id", "")
    if slot.get("name") == "manual" and len(sid) == 11 and sid.startswith("manual-"):
        return s["slot_manual"].format(hm=f"{sid[7:9]}:{sid[9:11]}")
    return slot["label"]


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


def _rows(ranked: list[dict], key: str, lang: str = "en") -> list[str]:
    out = []
    for i, p in enumerate(ranked, 1):
        if key == "total":
            out.append(f"| {i} | [{p['name']}](https://github.com/{p['name']}) | {p['stars']:,} |")
            continue
        g = p["growth"][key]
        mark = f" † ({S[lang]['young_div'].format(n=g['effective_days'])})" if g["young"] else ""
        out.append(f"| {i} | [{p['name']}](https://github.com/{p['name']}) | +{g['gained']:,} | "
                   f"{g['per_day']:,.1f}{mark} | {p['stars']:,} |")
    return out


def _new_rows(items: list[dict]) -> list[str]:
    return [f"| {i} | [{it['name']}]({it['url']}) | {it['created_at'][:10]} | {it['stars']:,} | "
            f"{it['per_day']:,.1f} |" for i, it in enumerate(items, 1)]


def render_rankings_md(stats: dict[str, Any], lang: str = "en") -> str:
    s = S[lang]
    slot = stats.get("slot") or {"label": s["snap_unlabelled"], "date": stats["today_utc"], "id": "n/a"}
    lines = [
        "# " + s["snap_title"].format(label=slot_label(slot, lang),
                                      date=slot["date"]), "",
        s["snap_meta"].format(id=slot["id"], ts=stats["generated_at"], end=stats["today_utc"], n=TOP_N), "",
    ]
    projects = stats["projects"]
    new = stats.get("newcomers")
    if new is not None:  # snapshots written before this ranking existed have no such key
        lines += [f"## {s['new']}", ""]
        if not new["ok"]:
            lines += [s["new_failed"].format(error=new["error"]), ""]
        else:
            lines += [f"| {s['h_rank']} | {s['h_repo']} | {s['h_created']} | {s['h_stars_short']} | {s['h_perday']} |",
                      "|---|---|---|---:|---:|"]
            lines += _new_rows(new["items"][:TOP_N]) + [""]
            bad = [q for q in new["queries"] if not q["ok"]]
            if bad:
                lines += [s["new_partial"].format(failed=len(bad), total=len(new["queries"])), ""]
    for key in ("week", "month", "year"):
        lines += [f"## {s[key]}", "",
                  f"| {s['h_rank']} | {s['h_project']} | {s['h_gain']} | {s['h_perday']} | {s['h_stars']} |",
                  "|---|---|---:|---:|---:|"]
        lines += _rows(core.rank(projects, key)[:TOP_N], key, lang) + [""]
    lines += [f"## {s['total']}", "", f"| {s['h_rank']} | {s['h_project']} | {s['h_stars']} |", "|---|---|---:|"]
    lines += _rows(core.rank(projects, "total")[:TOP_N], "total", lang) + [""]
    missing = [p for p in projects if not p.get("ok")]
    lines += [f"## {s['missing_title']}", ""]
    lines += [f"- `{p['name']}`: {p['error']}" for p in missing] if missing else [s["missing_none"]]
    lines += ["", s["snap_young"], ""]
    return "\n".join(lines)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")


def write_snapshot(root: Path, stats: dict[str, Any]) -> Path:
    slot = stats["slot"]
    d = root / "rankings" / slot["date"] / slot["id"]
    write_json(d / "stats.json", stats)
    for lang in LANGS:
        (d / rankings_name(lang)).write_text(render_rankings_md(stats, lang), "utf-8")
    return d


def scan_snapshots(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    found = []
    for f in sorted((root / "rankings").glob("*/*/stats.json")):
        found.append((f.parent, json.loads(f.read_text("utf-8"))))
    found.sort(key=lambda t: t[1]["generated_at"], reverse=True)
    return found


def render_index(root: Path, lang: str = "en") -> str:
    s = S[lang]
    rk = rankings_name(lang)
    snaps = scan_snapshots(root)
    lines = [
        "# " + s["idx_title"], "",
        s["idx_intro"], "",
        f"{s['idx_latest']}[`latest/{rk}`](../latest/{rk}) · [`latest/stats.json`](../latest/stats.json) · "
        f"[README](../{LANGS[lang][0]})", "",
        f"| {s['idx_h_date']} | {s['idx_h_slot']} | {s['idx_h_fetched']} | {s['idx_h_new']} | {s['idx_h_week']} | "
        f"{s['idx_h_month']} | {s['idx_h_year']} | {s['idx_h_snap']} |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d, st in snaps:
        slot = st["slot"]
        tops = []
        for key in ("week", "month", "year"):
            r = core.rank(st["projects"], key)
            per_day = f"{r[0]['growth'][key]['per_day']:,.0f}" if r else ""
            tops.append(f"{r[0]['name']} ({s['idx_perday'].format(n=per_day)})" if r else s["none"])
        new = st.get("newcomers")
        top_new = s["none"]
        if new and new.get("ok") and new["items"]:
            first = new["items"][0]
            top_new = f"{first['name']} ({s['idx_perday'].format(n=format(first['per_day'], ',.0f'))})"
        rel = d.relative_to(root / "rankings").as_posix()
        lines.append(f"| {slot['date']} | {slot_label(slot, lang)} (`{slot['id']}`) | {st['generated_at']} | "
                     f"{top_new} | {tops[0]} | {tops[1]} | {tops[2]} | [{rel}]({rel}/{rk}) · [json]({rel}/stats.json) |")
    if not snaps:
        lines.append(f"| | | | | | | | {s['idx_no_snaps']} |")
    lines.append("")
    return "\n".join(lines)


def render_latest_and_index(root: Path) -> dict[Path, str]:
    """Return {path: expected text} for latest/, the indexes and the localized snapshot pages.

    Derived from the committed stats.json files. The English snapshot page (rankings.md) is not
    listed: it is written once when the snapshot is created and then left alone.
    """
    out: dict[Path, str] = {root / "rankings" / index_name(lang): render_index(root, lang) for lang in LANGS}
    snaps = scan_snapshots(root)
    if snaps:
        newest = snaps[0][1]
        out[root / "latest/stats.json"] = json.dumps(newest, ensure_ascii=False, indent=2) + "\n"
        for lang in LANGS:
            out[root / "latest" / rankings_name(lang)] = render_rankings_md(newest, lang)
    for d, st in snaps:
        for lang in LANGS:
            if lang != "en":
                out[d / rankings_name(lang)] = render_rankings_md(st, lang)
    return out


def refresh_latest_and_index(root: Path) -> None:
    for path, text in render_latest_and_index(root).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, "utf-8")


def stale_latest_and_index(root: Path) -> list[str]:
    return [str(p.relative_to(root)) for p, t in render_latest_and_index(root).items()
            if not p.exists() or p.read_text("utf-8") != t]
