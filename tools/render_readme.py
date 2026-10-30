#!/usr/bin/env python3
"""Render README.md (English) and README.<lang>.md from data/*.json.

Usage: python tools/render_readme.py [--check]
  --check  exit 1 if any generated README differs from what is committed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive  # noqa: E402
import newcomers as nc  # noqa: E402
import newcomer_i18n  # noqa: E402
import risers_core as core  # noqa: E402
from i18n import LANGS, S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOP_N = archive.TOP_N  # rows in the full lists (latest/, rankings/)
README_TOP = 10  # rows per board in the README; the full top 20 is in latest/
REPO = "jammyfu/github-risers"
SITE = "https://jammyfu.github.io/github-risers/"
SOCIAL_IMAGE = ".github/social-preview.png"
# Anchors of docs/FAQ.md (written by the GEO work); only linked, never generated here.
FAQ_ANCHORS = ("what-is-github-risers", "is-it-the-same-as-github-trending", "how-often-is-it-updated")


def switcher(lang: str) -> str:
    parts = []
    for code, (fname, label) in LANGS.items():
        parts.append(f"**{label}**" if code == lang else f"[{label}]({fname})")
    return " | ".join(parts)


def how_name(lang: str) -> str:
    """File name (inside docs/) of the generated 'how it works' page for a language."""
    return "HOW_IT_WORKS.md" if lang == "en" else f"HOW_IT_WORKS.{lang}.md"


def anchor(heading: str) -> str:
    """GitHub's #fragment for a heading: lower-case, punctuation dropped, spaces to hyphens."""
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


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


def ordered_categories(cats: dict[str, dict]) -> list[dict]:
    return sorted(cats.values(), key=lambda c: (0 if c.get("primary") else 1, c.get("order", 99), c["id"]))


def category_block(cat: dict, st: list[dict], projects: list[dict], cats: dict,
                   newcomers_root: dict | None, lang: str, tr: dict | None) -> list[str]:
    """One category: newcomers, week, month, year, total."""
    s = S[lang]
    cid = cat["id"]
    out: list[str] = [
        f"## {cat['name'][lang]}", "",
        f"> {cat['desc'][lang]}", "",
    ]
    cat_projects = nc.projects_in_category(st, projects, cid)
    metas = {p["name"]: p for p in projects}

    # Newcomers for this category (new multi-cat shape, or legacy single list only under AI)
    new_block = None
    if newcomers_root is not None:
        if "categories" in newcomers_root:
            new_block = (newcomers_root.get("categories") or {}).get(cid)
        elif cid == "ai" or cat.get("primary"):
            new_block = newcomers_root  # legacy shape from older snapshots

    if new_block is not None:
        out += [f"### {s['new']}", ""]
        if not new_block.get("ok"):
            out += [s["new_failed"].format(error=new_block.get("error", "?")), ""]
        elif not new_block.get("items"):
            out += [s["new_none"], ""]
        else:
            out += [new_table(new_block["items"][:README_TOP], lang, tr), ""]
        if new_block.get("ok") and any(not q["ok"] for q in new_block.get("queries", [])):
            bad = sum(1 for q in new_block["queries"] if not q["ok"])
            out += [s["new_partial"].format(failed=bad, total=len(new_block["queries"])), ""]

    for key in ("week", "month", "year"):
        ranked = core.rank(cat_projects, key)[:README_TOP]
        out += [f"### {s[key]}", ""]
        if ranked:
            table, young = growth_table(ranked, key, metas, cats, lang)
            out += [table, ""]
            if young:
                out += [s["young"], ""]
        else:
            out += [s["none"], ""]

    ranked_total = core.rank(cat_projects, "total")[:README_TOP]
    out += [f"### {s['total']}", ""]
    if ranked_total:
        out += [total_table(ranked_total, metas, cats, lang), ""]
    else:
        out += [s["none"], ""]
    return out


def _rate(x: float) -> str:
    return f"{x:,.0f}" if x >= 100 else f"{x:,.1f}"


def _leader_cell(name: str | None, url: str | None, tail: str, lang: str) -> str:
    if not name:
        return S[lang]["none"]
    return f"[{name}]({url})<br>{tail}"


def leaders(stats: dict, projects: list[dict], cat_id: str, newcomers_block: dict | None) -> dict[str, dict | None]:
    """#1 of each board in one category, taken from the run's real data (None = board empty/missing)."""
    cat_stats = [p for p in stats["projects"] if p.get("category") == cat_id]
    out: dict[str, dict | None] = {}
    # a suspected crack / pirated repo is never a leader, even when it is the only entry
    normal = [i for i in (newcomers_block or {}).get("items", []) if not i.get("suspicious")]
    out["new"] = normal[0] if newcomers_block and newcomers_block.get("ok") and normal else None
    for key in ("week", "month", "year", "total"):
        r = core.rank(cat_stats, key)
        out[key] = r[0] if r else None
    return out


def tops_table(stats: dict, projects: list[dict], cats: dict, lang: str, link: bool = False) -> str:
    s = S[lang]
    metas = {p["name"]: p for p in projects}
    root = stats.get("newcomers") or {}
    lines = [
        f"| {s['tops_h_cat']} | {s['idx_h_new']} | {s['idx_h_week']} | {s['idx_h_month']} | {s['idx_h_year']} | {s['tops_h_total']} |",
        "|---|---|---|---|---|---|",
    ]
    for cat in ordered_categories(cats):
        if "categories" in root:
            block = (root.get("categories") or {}).get(cat["id"])
        else:
            block = root if cat.get("primary") else None
        led = leaders(stats, projects, cat["id"], block)
        cells = []
        n = led["new"]
        cells.append(_leader_cell(n["name"], n["url"], s["idx_perday"].format(n=_rate(n["per_day"])), lang) if n else s["none"])
        for key in ("week", "month", "year"):
            p = led[key]
            cells.append(_leader_cell(p["name"], metas[p["name"]]["url"],
                                      s["idx_perday"].format(n=_rate(p["growth"][key]["per_day"])), lang) if p else s["none"])
        p = led["total"]
        cells.append(_leader_cell(p["name"], metas[p["name"]]["url"], f"{fmt_int(p['stars'])} ★", lang) if p else s["none"])
        mark = f" ★ {s['primary_mark']}" if cat.get("primary") else ""
        name = cat["name"][lang]
        label = f"[{name}](#{anchor(name)})" if link else name  # the row name jumps to that category's boards
        lines.append(f"| **{label}**{mark} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def badges(stats: dict, lang: str) -> str:
    """Three badges, no more: licence, CI, last update."""
    day = stats["generated_at"][:10].replace("-", "--")  # shields.io: "--" is a literal hyphen
    return " ".join([
        "[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)",
        f"[![CI](https://github.com/{REPO}/actions/workflows/ci.yml/badge.svg)](https://github.com/{REPO}/actions/workflows/ci.yml)",
        f"[![updated](https://img.shields.io/badge/updated-{day}-brightgreen.svg)](latest/{archive.rankings_name(lang)})",
    ])


def faq_block(lang: str) -> list[str]:
    s = S[lang]
    out = [f"## {s['faq_title']}", ""]
    for i, anchor_ in enumerate(FAQ_ANCHORS, 1):
        out += [f"### {s[f'q{i}']}", "", f"{s[f'a{i}']} [{s['more']}](docs/FAQ.md#{anchor_})", ""]
    return out


def render(lang: str, projects: list[dict], stats: dict, cats: dict, tr: dict | None = None) -> str:
    """The README: headline, image, one sentence, this round's #1s, quick answers, then the boards (top 10)."""
    s = S[lang]
    st = stats["projects"]
    how = f"docs/{how_name(lang)}"
    latest = f"latest/{archive.rankings_name(lang)}"
    out: list[str] = [switcher(lang), ""]
    out += [
        f"# {s['title']}", "",
        f'<img src="{SOCIAL_IMAGE}" alt="{s["title"]}" width="640">', "",
        badges(stats, lang), "",
        s["tagline"], "",
        s["stamp"].format(ts=stats["generated_at"].replace("T", " ").replace("Z", "")[:16]), "",
        s["links"].format(website=s["website"], site=SITE, how=how, index=f"rankings/{archive.index_name(lang)}",
                          latest=latest), "",
        f"## {s['tops_title']}", "",
        tops_table(stats, projects, cats, lang, link=True), "",
        s["top_note"].format(latest=latest), "",
    ]
    out += faq_block(lang)
    newcomers_root = stats.get("newcomers")
    for cat in ordered_categories(cats):
        out += category_block(cat, st, projects, cats, newcomers_root, lang, tr)

    missing = [p for p in st if not p.get("ok")]
    if missing:  # only shown when something is actually missing
        out += [f"## {s['missing_title']}", "", s["missing_intro"], ""]
        out += [f"- `{p['name']}` — {p['error']}" for p in missing]
        out.append("")
    out += ["---", "", s["star_ask"], "", s["cite"], "", s["footer"].format(how=how), ""]
    return "\n".join(out)


def _docs_links(text: str) -> str:
    """Links written relative to the repo root, rewritten for a page that lives in docs/."""
    text = re.sub(r"\]\(docs/", "](", text)
    return re.sub(r"\]\(((?:data|rankings|latest)/)", r"](../\1", text)


def render_docs(lang: str, projects: list[dict], cats: dict) -> str:
    """docs/HOW_IT_WORKS*.md: everything the README no longer carries (intro, schedule, methodology, contributing)."""
    s = S[lang]
    sw = " | ".join(f"**{label}**" if code == lang else f"[{label}]({how_name(code)})"
                    for code, (_f, label) in LANGS.items())
    out: list[str] = [
        sw, "", f"# {s['doc_title']}", "",
        f"[{s['doc_back']}](../{LANGS[lang][0]})", "",
        s["intro"], "",
        s["schedule"], "",
        s["shown"].format(m=README_TOP, n=TOP_N, total=len(projects)), "",
        s["history"].format(index=f"rankings/{archive.index_name(lang)}", latest=f"latest/{archive.rankings_name(lang)}"), "",
        s["tops_intro"], "",
        f"## {s['cat_title']}", "",
        "| | |", "|---|---|",
    ]
    for c in ordered_categories(cats):
        mark = f" ★ {s.get('primary_mark', 'primary')}" if c.get("primary") else ""
        out.append(f"| {c['name'][lang]}{mark} | {c['desc'][lang]} |")
    out += ["", f"## {s['new']}", "", s["new_intro"], ""]
    out += [f"## {s['method_title']}", ""] + [f"- {m}" for m in s["method"]] + [""]
    out += [f"## {s['contrib_title']}", "", s["contrib"], ""]
    return _docs_links("\n".join(out))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    projects = json.loads((ROOT / "data/projects.json").read_text("utf-8"))
    cats = {c["id"]: c for c in json.loads((ROOT / "data/categories.json").read_text("utf-8"))}
    stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))
    tr = newcomer_i18n.load(ROOT / "data/translation_library.json")
    stale = []
    for lang, (fname, _label) in LANGS.items():
        for rel, text in ((fname, render(lang, projects, stats, cats, tr)),
                          (f"docs/{how_name(lang)}", render_docs(lang, projects, cats))):
            path = ROOT / rel
            if args.check:
                if not path.exists() or path.read_text("utf-8") != text:
                    stale.append(rel)
            else:
                path.write_text(text, "utf-8")
                print(f"wrote {rel}")
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
