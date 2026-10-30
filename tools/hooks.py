#!/usr/bin/env python3
"""One-line hooks for the ranking tables.

Every row of a board shows ONE short, plain, catchy sentence (the "hook"), not the full description:
what the project lets you do, in words a beginner understands at a glance. Everything else (tool names,
file formats, the long original wording) stays in the detail text and is listed on docs/DETAILS*.md.

Where hooks live:
  data/projects.json                      "hook": {lang: text}   next to "desc" (= the detail text)
  data/translation_library.json           slot["hook"] = {lang: text}   next to the translations of a source text
                                          (same repo + source-hash key, so a changed source needs a new hook)

The length limits below are enforced by `check_hook` (the pipeline rejects longer hooks and keeps the old
text) and by tests/test_hooks.py (every stored hook must obey them, in every language).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

LANGS = ("en", "zh-Hans", "zh-Hant", "ja", "ko")

# Display width, so CJK text (2 columns per character) and Latin names (1 column) share one rule.
# Roughly: zh <= 18 Chinese characters, ja <= 28 characters, ko <= 30 characters, en <= 60 letters.
MAX_WIDTH = {"en": 60, "zh-Hans": 36, "zh-Hant": 36, "ja": 56, "ko": 60}
GOAL = {"en": "about 45 characters", "zh-Hans": "about 15 Chinese characters", "zh-Hant": "about 15 Chinese characters",
        "ja": "about 25 Japanese characters", "ko": "about 25 Korean characters"}

HOOK_RULE = (
    "HOOK RULE: each ranking row shows ONE short hook per language. A hook is a single plain, catchy sentence "
    "(or fragment) that says what the project lets you DO, so a beginner gets it at a glance. "
    "Example: \"Let AI reverse-engineer and clone any software\" / 「让 AI 帮你逆向、复刻任何软件」. "
    "Limits (hard): English <= {en} characters; Simplified/Traditional Chinese <= 18 Chinese characters "
    "(aim for about 15); Japanese <= 28 characters; Korean <= 30 characters. "
    "Use everyday words; lead with the benefit; drop file formats, tool names, version lists and credits "
    "(they stay in the detail text, nothing is lost). Never invent a fact, number or claim that the source does not state; "
    "no exclamation marks, no hype or clickbait words, no trailing \"…\". One line, no markdown, no quotes. "
    "For repos that look cracked / pirated / pre-activated, do not make them attractive: a flat literal label "
    "(for example \"<name> 2026 installer, listed as pre-activated\")."
).format(**{"en": MAX_WIDTH["en"]})

HYPE = re.compile(
    r"炸裂|颠覆|顛覆|震惊|震驚|史诗|史詩|封神|吊打|逆天|神器|重磅|必看|绝绝子|絕絕子|"
    r"game[- ]?changer|revolutionary|mind[- ]?blowing|insane|you won't believe|ヤバい|衝撃|革命的|충격|혁명적",
    re.I)
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def width(text: str) -> int:
    """Display columns: wide / fullwidth characters (CJK, kana, hangul, emoji) count 2, the rest 1."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def limit(lang: str) -> int:
    return MAX_WIDTH[lang]


def _nums(text: str) -> set[str]:
    """Numbers of 2+ digits: a single digit may legitimately turn into a word or back ("second AI" -> "2 AIs")."""
    return {n for n in (m.replace(",", "").rstrip(".") for m in _NUM.findall(text)) if len(n) >= 2}


def check_hook(hook: Any, lang: str, detail: str = "") -> str | None:
    """None if `hook` is an acceptable hook in `lang`, else the reason it is rejected.

    `detail` is the text the hook was written from: a hook may not contain a number that the detail does not.
    """
    if not isinstance(hook, str) or not hook.strip():
        return "empty"
    hook = hook.strip()
    if "\n" in hook or "```" in hook or hook[0] in "\"'“「" and hook[-1] in "\"'”」":
        return "not a single plain line"
    if width(hook) > limit(lang):
        return f"too long for a hook ({width(hook)} > {limit(lang)} columns)"
    if re.search(r"[!！]", hook) or hook.endswith(("…", "...")):
        return "exclamation mark or ellipsis"
    if HYPE.search(hook) and not HYPE.search(detail):
        return "hype wording"
    if detail and _nums(hook) - _nums(detail):
        return "a number that is not in the source"
    return None


def pick(hooks: dict[str, str] | None, lang: str, fallback: str) -> str:
    """The stored hook for `lang`, else `fallback` (the long text: shown only until a hook exists)."""
    text = ((hooks or {}).get(lang) or "").strip()
    return text or fallback
