#!/usr/bin/env python3
"""Translation library for the new-repo descriptions (data/translation_library.json).

The "hottest new repos" ranking shows each repo's own GitHub description. The library stores its
translations keyed exactly by  repo + hash of the source text + language:

    { "version": 2,
      "entries": { "owner/repo": { "<sha256(src)[:12]>": { "src": "<the description>", "seen": "YYYY-MM-DD",
                                                           "zh-Hans": "...", "zh-Hant": "...", "ja": "...", "ko": "...", "en": "...",
                                                           "hook": { "en": "...", "zh-Hans": "...", ... } } } } }

* Hit  = the (repo, source hash) entry has the language: the stored text is used, no model is involved.
* Miss = the source text is new or changed: only then a model is asked, and only for the missing languages.
* Older versions of a description stay in the library (a description that changes back is a hit again);
  `seen` is the last day the entry was used (refreshed at most weekly) so `--prune-days N` can drop dead ones.
* `hook` = the one-line text the ranking tables show (see tools/hooks.py); the translations above are the detailed
  text (docs/DETAILS*.md). Adding a hook never changes a translation, and a missing hook never counts as a translation gap.
* The original text is shown for any language without a hit; a translation of a text that has since changed is never shown.

Entries are added by tools/i18n_pipeline.py during the update (or by hand).
Usage:
  python tools/newcomer_i18n.py                  list repos in the current ranking that lack a translation, and the hit rate
  python tools/newcomer_i18n.py --strict         same, but exit 1 if a primary (AI) description is missing
  python tools/newcomer_i18n.py --prune-days N   drop entries not used for N days (and write the file)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "data/translation_library.json"
VERSION = 2
SEEN_REFRESH_DAYS = 7
# Languages every entry must have. "en" is optional and only expected when the source has CJK text.
REQUIRED = ("zh-Hans", "zh-Hant", "ja", "ko")
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
_COMMENT = ("Translation library for new-repo descriptions, keyed by repo + sha256(source)[:12] + language. "
            "Used by tools/newcomer_i18n.py and tools/i18n_pipeline.py; see docs/I18N_PIPELINE.md.")

Library = dict[str, Any]


def src_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def empty() -> Library:
    return {"_comment": _COMMENT, "version": VERSION, "entries": {}}


def from_legacy(old: dict[str, dict[str, str]], seen: str | None = None) -> Library:
    """Convert the version-1 shape {repo: {"src": ..., lang: text}} into a library."""
    lib = empty()
    for name, entry in old.items():
        if name.startswith("_") or not isinstance(entry, dict) or "src" not in entry:
            continue
        slot = {k: v for k, v in entry.items()}
        if seen:
            slot["seen"] = seen
        lib["entries"].setdefault(name, {})[src_hash(entry["src"])] = slot
    return lib


def load(path: Path = CACHE_PATH) -> Library:
    if not path.exists():
        return empty()
    data = json.loads(path.read_text("utf-8"))
    if "entries" not in data:  # version-1 file: still readable
        return from_legacy(data)
    data.setdefault("entries", {})
    return data


def save(lib: Library, path: Path = CACHE_PATH) -> None:
    lib["_comment"], lib["version"] = _COMMENT, VERSION
    lib["entries"] = {n: dict(sorted(v.items())) for n, v in sorted(lib["entries"].items())}
    path.write_text(json.dumps(lib, ensure_ascii=False, indent=2) + "\n", "utf-8")


def lookup(lib: Library, name: str, description: str) -> dict[str, str] | None:
    return (lib.get("entries", {}).get(name) or {}).get(src_hash(description))


def get(lib: Library, name: str, description: str, lang: str) -> str | None:
    entry = lookup(lib, name, description)
    text = (entry or {}).get(lang, "")
    return text if text.strip() else None


def put(lib: Library, name: str, description: str, lang: str, text: str, today: str | None = None) -> None:
    slot = lib["entries"].setdefault(name, {}).setdefault(src_hash(description), {"src": description})
    slot[lang] = text
    if today:
        slot["seen"] = today


def get_hook(lib: Library, name: str, description: str, lang: str) -> str | None:
    """The one-line hook (tools/hooks.py) stored next to the translations of this exact source text, if any."""
    text = (((lookup(lib, name, description) or {}).get("hook") or {}).get(lang) or "")
    return text if text.strip() else None


def put_hook(lib: Library, name: str, description: str, lang: str, text: str, today: str | None = None) -> None:
    """Store a hook. Only the `hook` sub-dict changes: translations already in the entry are never touched."""
    slot = lib["entries"].setdefault(name, {}).setdefault(src_hash(description), {"src": description})
    old = (slot.get("hook") or {}).get(lang)
    if old and old != text:  # an earlier hook is kept (never shown), not overwritten
        slot.setdefault("hook_prev", {})[lang] = old
    slot.setdefault("hook", {})[lang] = text
    if today:
        slot["seen"] = today


def touch(lib: Library, name: str, description: str, today: str) -> bool:
    """Mark an entry as used today (at most once per SEEN_REFRESH_DAYS). True if the library changed."""
    slot = lookup(lib, name, description)
    if slot is None:
        return False
    last = slot.get("seen")
    if last:
        try:
            if (dt.date.fromisoformat(today) - dt.date.fromisoformat(last)).days < SEEN_REFRESH_DAYS:
                return False
        except ValueError:
            pass
    slot["seen"] = today
    return True


def prune(lib: Library, today: str, keep_days: int) -> int:
    """Drop entries unused for more than keep_days (entries without `seen` are kept). Returns how many."""
    cutoff = dt.date.fromisoformat(today) - dt.timedelta(days=keep_days)
    gone = 0
    for name in list(lib["entries"]):
        for h, slot in list(lib["entries"][name].items()):
            try:
                old = bool(slot.get("seen")) and dt.date.fromisoformat(slot["seen"]) < cutoff
            except ValueError:
                old = False
            if old:
                del lib["entries"][name][h]
                gone += 1
        if not lib["entries"][name]:
            del lib["entries"][name]
    return gone


def pick(lib: Library, name: str, description: str, lang: str) -> str:
    """The stored translation of `description` into `lang` if there is a hit, else the original."""
    return get(lib, name, description, lang) or description


def required_langs(description: str) -> tuple[str, ...]:
    return REQUIRED + (("en",) if _CJK.search(description) else ())


def missing_langs(lib: Library, name: str, description: str) -> list[str]:
    """Languages of `description` that still need a translation (all required ones if there is no entry)."""
    entry = lookup(lib, name, description) or {}
    return [l for l in required_langs(description) if not entry.get(l, "").strip()]


def problems(lib: Library, items: list[dict[str, Any]]) -> list[str]:
    """One line per repo in the ranking whose description has no (complete) translation for its current text."""
    out = []
    for it in items:
        desc = it.get("description") or ""
        if not desc:
            continue
        lacking = missing_langs(lib, it["name"], desc)
        if len(lacking) == len(required_langs(desc)):
            known = lib.get("entries", {}).get(it["name"])
            out.append(f"{it['name']}: " + ("changed since it was translated" if known else "missing (all languages)"))
        elif lacking:
            out.append(f"{it['name']}: missing {', '.join(lacking)}")
    return out


def hit_stats(lib: Library, items: list[dict[str, Any]]) -> dict[str, int]:
    """Counts over the ranked descriptions: total, full hits (every language stored), partial, new."""
    total = hits = partial = new = 0
    for it in items:
        desc = (it.get("description") or "").strip()
        if not desc:
            continue
        total += 1
        lacking = missing_langs(lib, it["name"], it["description"])
        if not lacking:
            hits += 1
        elif len(lacking) < len(required_langs(it["description"])):
            partial += 1
        else:
            new += 1
    return {"total": total, "hits": hits, "partial": partial, "new": new}


def ranked_items(new: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(all ranked items, items of the primary AI category) from stats['newcomers'] (either shape)."""
    items: list[dict[str, Any]] = []
    primary: list[dict[str, Any]] = []
    if new and new.get("ok"):
        if "categories" in new:
            for cid, block in (new.get("categories") or {}).items():
                if block.get("ok"):
                    chunk = block.get("items") or []
                    items.extend(chunk)
                    if cid == "ai":
                        primary = chunk
        else:
            items = primary = new.get("items") or []
    return items, primary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="exit 1 if a primary (AI) description lacks a translation")
    ap.add_argument("--prune-days", type=int, help="drop library entries not used for N days and write the file")
    args = ap.parse_args(argv)
    lib = load()
    if args.prune_days is not None:
        gone = prune(lib, dt.date.today().isoformat(), args.prune_days)
        save(lib)
        print(f"pruned {gone} entries unused for more than {args.prune_days} days")
    stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))
    items, primary_items = ranked_items(stats.get("newcomers"))
    bad = problems(lib, items)
    hs = hit_stats(lib, items)
    n_entries = sum(len(v) for v in lib["entries"].values())
    print(f"library: {n_entries} entries for {len(lib['entries'])} repos; ranked now: {hs['hits']}/{hs['total']} hits")
    if bad:
        print(f"{len(bad)} of {len(items)} new-repo descriptions need a translation "
              f"(tools/i18n_pipeline.py --translate adds them):")
        print("\n".join(f"  - {line}" for line in bad))
    else:
        print(f"all {len(items)} new-repo descriptions are translated")
    # --strict only gates the primary (AI) category so daily runs across many categories stay usable
    strict_bad = problems(lib, primary_items) if args.strict else []
    if args.strict and strict_bad:
        print(f"--strict: {len(strict_bad)} primary (AI) descriptions still need a translation")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
