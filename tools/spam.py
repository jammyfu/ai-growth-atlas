"""Heuristics that keep cracked / pirated / "activator" repos out of the newcomer boards.

These repos farm stars with commercial-software names ("Canva-Pro", "Adobe-Acrobat-Pro",
"KMS-Pico") and canned descriptions ("full working installer", "pre-activated").
`suspicious_reason(repo)` returns a short reason string, or None when the repo looks fine.
It only reads fields the GitHub API already returns (full_name, description, topics).
Rules are documented in docs/CATEGORIES.md; tests/test_spam.py guards against regressions.
"""
from __future__ import annotations

import re
from typing import Any

# Phrases that essentially only appear in crack / activator / pirated-installer repos.
PHRASES = re.compile(
    r"\b(crack(?:ed|s)?|keygen|key[- ]?gen|activator|pre[- ]?activated|kms[- ]?pico|kmspico|kmsauto|"
    r"free[- ]download|download[- ]free|free[- ]full[- ]version|full[- ]version|"
    r"serial[- ]?(?:key|number)s?|license[- ]key|product[- ]key|warez|nulled|repack|"
    r"mod[- ]?apk|premium[- ]unlocked|all[- ]features[- ]unlocked|features[- ]unlocked|"
    r"standalone[- ]setup|full[- ]working[- ]installer|working[- ]installer|"
    r"ready[- ]to[- ]run[- ]desktop|lifetime[- ]activation|activation[- ]key|no[- ]license[- ]needed)\b",
    re.I,
)
# "<something> 2026 ... installer/setup/edition" style spam copy.
YEAR_INSTALLER = re.compile(r"\b20\d\d\b.{0,80}\b(installer|setup|edition|desktop)\b", re.I)
# Release-note-only descriptions used by throwaway repos.
PUBLISHED_ONLY = re.compile(r"^\s*published:\s*\d{4}-\d{2}-\d{2}\s*$", re.I)

# Commercial software names. A repo whose NAME contains one of these is dropped unless the owner is the vendor.
BRANDS = [
    "adobe", "photoshop", "illustrator", "premiere", "after-?effects", "lightroom", "indesign", "acrobat",
    "canva", "autocad", "autodesk", "solidworks", "sketchup", "cinema-?4d", "designcenter", "substance",
    "microsoft-?office", "office-?365", "windows-?(?:7|8|10|11)", "wondershare", "corel(?:draw)?", "winrar",
    "systemcare", "camtasia", "filmora", "vegas-?pro", "fl-?studio", "ableton", "topaz", "idm",
    "internet-?download-?manager", "nitro-?pdf", "revit", "matlab", "sketch-?pro", "capcut-?pro",
]
BRAND_RE = re.compile(r"(?<![a-z0-9])(?:" + "|".join(BRANDS) + r")(?![a-z0-9])", re.I)
# vendor-owned repos are fine (adobe/spectrum, autodesk/..., canva/...)
VENDOR_OWNERS = ("adobe", "autodesk", "canva", "microsoft", "corel", "wondershare", "mathworks", "trimble")
# "<name>-Pro", "<name> Premium" ... in the repo name
PRO_SUFFIX = re.compile(r"[-_. ](pro|premium|full|free|cracked|portable|2023|2024|2025|2026)(?:[-_. ]|$)", re.I)


def suspicious_reason(repo: dict[str, Any]) -> str | None:
    full = repo.get("full_name") or repo.get("name") or ""
    owner, _, name = full.partition("/")
    desc = repo.get("description") or ""
    topics = " ".join(repo.get("topics") or [])
    hay = f"{name} {desc} {topics}"
    m = PHRASES.search(hay)
    if m:
        return f"phrase:{m.group(0).lower()}"
    if YEAR_INSTALLER.search(desc):
        return "year-installer copy"
    if PUBLISHED_ONLY.match(desc):
        return "release-note-only description"
    b = BRAND_RE.search(name)
    if b and not owner.lower().startswith(VENDOR_OWNERS):
        return f"commercial-software name:{b.group(0).lower()}"
    if PRO_SUFFIX.search(name) and not desc.strip() and not repo.get("language"):
        return "-Pro/-Premium name with no description or language"
    return None
