#!/usr/bin/env python3
"""One-line hooks for the ranking tables.

Every row of a board shows ONE short, plain, catchy sentence (the "hook"), not the full description:
what the project lets you do, in words a beginner understands at a glance. Everything else (tool names,
file formats, the long original wording) stays in the detail text and is listed on docs/DETAILS*.md.

Where hooks live:
  data/projects.json                      "hook": {lang: text}   next to "desc" (= the detail text);
                                          "hook_prev": the hook before the last rewrite (kept, never shown)
  data/translation_library.json           slot["hook"] = {lang: text}   next to the translations of a source text
                                          (same repo + source-hash key, so a changed source needs a new hook);
                                          slot["hook_prev"] keeps the previous hook the same way

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

# The eight writing rules for ad-grade hooks (from the 2026-10-31 zh-Hans slogan set). Every one of them is in the prompt.
WRITING_RULES = (
    "Start from the reader's trouble, then say what the project fixes: find the pain in the source text, never start from a technical noun.",
    "Say only what the source states: add no feature, number, effect or platform; if the source does not say open source, free or local, you do not say it either.",
    "Write for someone who has never seen it: say \"install packages\", not \"dependency resolution\"; say \"AI remembers last time\", not \"cross-session memory\".",
    "One sentence sells ONE benefit; drop the minor features rather than listing them.",
    "Short enough to read at a glance (limits below); no exclamation marks, no ellipsis, no hype words.",
    "Use everyday actions and pictures: look, find, install, draw, switch, scan, manage; few abstract nouns.",
    "Security / compliance: plain words about what is checked and what is kept out, never scary; cracked, pirated or limit-bypassing projects are never turned into a selling point.",
    "A brand name is not a reason: official / big-company / famous-author appears only when the source says it and it really helps understanding, never in place of the user's benefit.",
)

HOOK_RULE = (
    "HOOK RULE: each ranking row shows ONE ad-grade hook per language (a single plain, catchy sentence or fragment). "
    "Example: \"Can't read a program? Let AI explain it to you\" / 「看不懂的程序，让 AI 讲给你听」. "
    "Write it as a copywriter in that language would (benefit first, natural rhythm), not as a word-for-word translation: "
    "all languages carry the same meaning and flavour. "
    "Eight writing rules: "
    + " ".join(f"({i}) {r}" for i, r in enumerate(WRITING_RULES, 1))
    + " Hard limits: English <= {en} characters; Simplified/Traditional Chinese <= 18 Chinese characters "
    "(aim for about 15); Japanese <= 28 characters; Korean <= 30 characters. "
    "Tool names, file formats, version lists and credits stay in the detail text (nothing is lost). "
    "No trailing \"…\", one line, no markdown, no quotes. "
    "For repos that look cracked / pirated / pre-activated, write a flat literal label "
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
