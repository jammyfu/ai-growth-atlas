#!/usr/bin/env python3
"""Render README.md (English) and README.<lang>.md from data/*.json.

Usage: python tools/render_readme.py [--check]
  --check  exit 1 if any generated README differs from what is committed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive  # noqa: E402
import atlas_core as core  # noqa: E402
import newcomer_i18n  # noqa: E402
from i18n import LANGS, S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOP_N = archive.TOP_N


def switcher(lang: str) -> str:
    parts = []
    for code, (fname, label) in LANGS.items():
        parts.append(f"**{label}**" if code == lang else f"[{label}]({fname})")
    return " | ".join(parts)


def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_rate(x: float) -> str:
    return f"{x:,.1f}"


def curve_cell(name: str, lang: str) -> str:
    alt = S[lang]["curve_alt"].format(name=name)
    return (f'<a href="{core.star_history_page(name)}">'
            f'<img src="{core.star_history_svg(name)}" width="260" alt="{alt}"></a>')


def project_cell(p: dict, meta: dict, cats: dict, lang: str) -> str:
    cat = cats.get(meta["category"], {}).get("name", {}).get(lang, meta["category"])
    return f"[{p['name']}]({meta['url']})<br>{meta['desc'][lang]}<br>`{cat}`"


def growth_table(ranked: list[dict], key: str, metas: dict, cats: dict, lang: str) -> tuple[str, bool]:
    s = S[lang]
    lines = [
        f"| {s['h_rank']} | {s['h_project']} | {s['h_gain']} | {s['h_perday']} | {s['h_stars']} | {s['h_curve']} |",
        "|---|---|---:|---:|---:|---|",
    ]
    any_young = False
    for i, p in enumerate(ranked, 1):
        g = p["growth"][key]
        mark = ""
        if g["young"]:
            mark = f" †<br><sub>{s['young_div'].format(n=g['effective_days'])}</sub>"
            any_young = True
        lines.append(
            f"| {i} | {project_cell(p, metas[p['name']], cats, lang)} | +{fmt_int(g['gained'])} | "
            f"{fmt_rate(g['per_day'])}{mark} | {fmt_int(p['stars'])} | {curve_cell(p['name'], lang)} |"
        )
    return "\n".join(lines), any_young


def total_table(ranked: list[dict], metas: dict, cats: dict, lang: str) -> str:
    s = S[lang]
    lines = [
        f"| {s['h_rank']} | {s['h_project']} | {s['h_stars']} | {s['h_curve']} |",
        "|---|---|---:|---|",
    ]
    for i, p in enumerate(ranked, 1):
        lines.append(f"| {i} | {project_cell(p, metas[p['name']], cats, lang)} | "
                     f"{fmt_int(p['stars'])} | {curve_cell(p['name'], lang)} |")
    return "\n".join(lines)


def new_table(items: list[dict], lang: str, tr: dict | None = None) -> str:
    s = S[lang]
    tr = tr or {}
    lines = [
        f"| {s['h_rank']} | {s['h_project']} | {s['h_created']} | {s['h_stars']} | {s['h_perday']} | {s['h_curve']} |",
        "|---|---|---|---:|---:|---|",
    ]
    for i, it in enumerate(items, 1):
        text = newcomer_i18n.pick(tr, it["name"], it["description"], lang) if it["description"] else ""
        desc = f"<br>{text}" if text else ""
        lines.append(
            f"| {i} | [{it['name']}]({it['url']}){desc} | {it['created_at'][:10]}<br><sub>{s['age_fmt'].format(x=it['age_days'])}</sub> | "
            f"{fmt_int(it['stars'])} | {fmt_rate(it['per_day'])} | {curve_cell(it['name'], lang)} |")
    return "\n".join(lines)


def render(lang: str, projects: list[dict], stats: dict, cats: dict, tr: dict | None = None) -> str:
    s = S[lang]
    metas = {p["name"]: p for p in projects}
    st = stats["projects"]
    out: list[str] = [
        switcher(lang), "",
    ]
    if lang == "en":
        out += ["> 💡 **中文读者请看**：[简体中文版 👉](README.zh-Hans.md)", ""]
    out += [
        f"# {s.get('title', 'AI Growth Atlas')}", "",
        f"> {s['tagline']}", "",
        s["intro"], "",
        s["updated"].format(ts=stats["generated_at"].replace("T", " ").replace("Z", "")),
        s["shown"].format(n=TOP_N, total=len(projects)), "",
        s["history"].format(index=f"rankings/{archive.index_name(lang)}",
                            latest=f"latest/{archive.rankings_name(lang)}"), "",
        f"<details><summary>{s['cat_title']}</summary>", "",
        "| | |", "|---|---|",
    ]
    for c in cats.values():
        out.append(f"| {c['name'][lang]} | {c['desc'][lang]} |")
    out += ["", "</details>", ""]

    new = stats.get("newcomers")
    if new is not None:
        out += [f"## {s['new']}", "", s["new_intro"], ""]
        if not new["ok"]:
            out += [s["new_failed"].format(error=new["error"]), ""]
        elif not new["items"]:
            out += [s["new_none"], ""]
        else:
            out += [new_table(new["items"][:TOP_N], lang, tr), ""]
        if new["ok"] and any(not q["ok"] for q in new["queries"]):
            bad = sum(1 for q in new["queries"] if not q["ok"])
            out += [s["new_partial"].format(failed=bad, total=len(new["queries"])), ""]

    for key in ("week", "month", "year"):
        ranked = core.rank(st, key)[:TOP_N]
        out += [f"## {s[key]}", ""]
        if ranked:
            table, young = growth_table(ranked, key, metas, cats, lang)
            out += [table, ""]
            if young:
                out += [s["young"], ""]
        else:
            out += [s["none"], ""]

    out += [f"## {s['total']}", "", total_table(core.rank(st, "total")[:TOP_N], metas, cats, lang), ""]

    missing = [p for p in st if not p.get("ok")]
    out += [f"## {s['missing_title']}", ""]
    if missing:
        out += [s["missing_intro"], ""]
        out += [f"- `{p['name']}` — {p['error']}" for p in missing]
        out.append("")
    else:
        out += [s["missing_none"], ""]

    out += [f"## {s['method_title']}", ""] + [f"- {m}" for m in s["method"]] + [""]
    out += [f"## {s['contrib_title']}", "", s["contrib"], ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    projects = json.loads((ROOT / "data/projects.json").read_text("utf-8"))
    cats = {c["id"]: c for c in json.loads((ROOT / "data/categories.json").read_text("utf-8"))}
    stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))
    tr = newcomer_i18n.load(ROOT / "data/newcomer_i18n.json")
    stale = []
    for lang, (fname, _label) in LANGS.items():
        text = render(lang, projects, stats, cats, tr)
        path = ROOT / fname
        if args.check:
            if not path.exists() or path.read_text("utf-8") != text:
                stale.append(fname)
        else:
            path.write_text(text, "utf-8")
            print(f"wrote {fname}")
    if args.check:
        stale += archive.stale_latest_and_index(ROOT)
    else:
        archive.refresh_latest_and_index(ROOT)
    if stale:
        print("stale (run python tools/render_readme.py): " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
