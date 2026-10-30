#!/usr/bin/env python3
"""Hand-written translations of the new-repo descriptions (data/newcomer_i18n.json).

The "hottest new repos" ranking shows each repo's own GitHub description. This cache maps a repo
full name to {"src": <description it was translated from>, "<lang>": <translation>, ...}.
A translation is used only when `src` still equals the current description; otherwise the original
text is shown (it never shows a translation of a text that has since changed). No online
translation, no keys: entries are added by hand.

Usage:
  python tools/newcomer_i18n.py            list repos in the current ranking that lack a translation
  python tools/newcomer_i18n.py --strict   same, but exit 1 if anything is missing or stale
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "data/newcomer_i18n.json"
# Languages every entry must have. "en" is optional and only expected when the source has CJK text.
REQUIRED = ("zh-Hans", "zh-Hant", "ja", "ko")
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def load(path: Path = CACHE_PATH) -> dict[str, dict[str, str]]:
    return json.loads(path.read_text("utf-8")) if path.exists() else {}


def pick(cache: dict[str, dict[str, str]], name: str, description: str, lang: str) -> str:
    """The translation of `description` into `lang` if a current one exists, else the original."""
    entry = cache.get(name)
    if entry and entry.get("src") == description and entry.get(lang, "").strip():
        return entry[lang]
    return description


def required_langs(description: str) -> tuple[str, ...]:
    return REQUIRED + (("en",) if _CJK.search(description) else ())


def problems(cache: dict[str, dict[str, str]], items: list[dict[str, Any]]) -> list[str]:
    """One line per repo in the ranking whose description is untranslated (missing) or stale."""
    out = []
    for it in items:
        desc = it.get("description") or ""
        if not desc:
            continue
        entry = cache.get(it["name"])
        if entry is None:
            out.append(f"{it['name']}: missing (all languages)")
        elif entry.get("src") != desc:
            out.append(f"{it['name']}: stale (description changed since it was translated)")
        else:
            lacking = [l for l in required_langs(desc) if not entry.get(l, "").strip()]
            if lacking:
                out.append(f"{it['name']}: missing {', '.join(lacking)}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="exit 1 if any translation is missing or stale")
    args = ap.parse_args(argv)
    stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))
    new = stats.get("newcomers") or {}
    items = new.get("items", []) if new.get("ok") else []
    bad = problems(load(), items)
    if bad:
        print(f"{len(bad)} of {len(items)} new-repo descriptions need a translation "
              f"(add them to data/newcomer_i18n.json):")
        print("\n".join(f"  - {line}" for line in bad))
    else:
        print(f"all {len(items)} new-repo descriptions are translated")
    return 1 if (bad and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
