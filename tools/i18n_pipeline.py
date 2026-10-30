#!/usr/bin/env python3
"""Translate new-repo descriptions, write one-line hooks and polish all copy, as part of the scheduled update.

Three stages, all optional and all fail-safe (any problem leaves the existing text in place and
never fails the update):

1. translate  every description in the new-repos ranking that has no current translation
              (data/translation_library.json, keyed by repo + hash of the source text + language: a hit costs
              no model call) -> zh-Hans, zh-Hant, ja, ko (+ en if the source
              contains CJK text).
2. hooks      the ranking tables show ONE short catchy line per repo (tools/hooks.py: zh <= ~15 characters,
              en <= 60, ja/ko equally short). Every repo whose current text has no hook yet (or whose stored hook
              breaks the length rule) gets one, in all five languages, in the same call style as translate. A hook
              is stored NEXT TO the translations (never in place of them): the long description and every translation
              stay exactly as they are and are listed on docs/DETAILS*.md.
3. polish     rewrite the project blurbs (data/projects.json), the translated new-repo descriptions
              and, only on request, the category descriptions in a short, plain, lead-with-the-point
              voice. Each text is polished once: data/polish_state.json remembers the hash of the text
              that was polished, so unchanged text is never sent again. A polished text is accepted
              only if it passes the guards in `check_polished`; otherwise the previous text stays.

Both stages call an agent CLI through tools/llm.py, model gemini-3.8-flash-medium by default
(POLISH_MODEL / I18N_TRANSLATE_MODEL):
  translate  backend I18N_TRANSLATE_BACKEND, default "cursor" (Cursor CLI, key CURSOR_API_KEY: the CI step)
  hooks      backend I18N_HOOK_BACKEND,      default = the translate backend (so new repos get a hook in CI too)
  polish     backend I18N_POLISH_BACKEND,    default "agy"    (Antigravity CLI on the owner's machine)
Without the CLI / sign-in / key, or when the model is not offered, the stage is skipped with a message.
CI runs translate only; polish is run locally (tools/polish_local.sh, or tools/local_daily.sh).

Usage: python3 tools/i18n_pipeline.py [--translate] [--hooks] [--polish] [--targets newcomers,projects,categories]
                                      [--limit N] [--dry-run]
       (no stage flag = all stages)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Protocol

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hooks  # noqa: E402
import llm  # noqa: E402
import newcomer_i18n as nci  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data/polish_state.json"
LIB_REL = "data/translation_library.json"
GLOSSARY_REL = "data/glossary.json"
LANGS = ("en", "zh-Hans", "zh-Hant", "ja", "ko")
TOP_N = 20
POLISH_VERSION = 1          # bump to re-polish everything after changing the style prompt
BATCH = 8
MAX_FAILS = 3               # a text whose polish was rejected this often is left alone until it changes
MAX_CONSECUTIVE_ERRORS = 3  # stop a stage after this many failed calls in a row
DEFAULT_BUDGET_SEC = 900
DEFAULT_TARGETS = ("newcomers", "projects")

LANG_NAMES = {
    "en": "English",
    "zh-Hans": "Simplified Chinese (简体中文, mainland usage)",
    "zh-Hant": "Traditional Chinese (繁體中文, Taiwan/Hong Kong usage, not mainland wording)",
    "ja": "Japanese (日本語, plain 常体 style: 〜する／〜できる, not です・ます)",
    "ko": "Korean (한국어, plain 해라체 style: ~한다 / ~할 수 있다)",
}
BASE_RULES = "Product, repo, company and model names stay exactly as written."


def load_glossary(root: Path) -> dict[str, Any]:
    path = root / GLOSSARY_REL
    return json.loads(path.read_text("utf-8")) if path.exists() else {"terms": [], "keep": []}


def glossary_for(texts: list[str], langs: list[str], glossary: dict[str, Any]) -> str:
    """Only the glossary terms that occur in `texts`, for `langs`: keeps the prompt (and token bill) small."""
    blob = "\n".join(texts).lower()
    lines = []
    for t in glossary.get("terms", []):
        if re.search(r"(?<![a-z])" + re.escape(t["en"].lower()) + r"s?(?![a-z])", blob):
            lines.append(t["en"] + " = " + " / ".join(f"{t[l]} ({l})" for l in langs if l != "en" and t.get(l)))
    keep = [k for k in glossary.get("keep", []) if k.lower() in blob]
    out = BASE_RULES
    if lines:
        out += " Fixed terms: " + "; ".join(lines) + "."
    if keep:
        out += " Keep as is: " + ", ".join(keep) + "."
    return out


TRANSLATE_PROMPT = """You translate short GitHub project descriptions. Reply with ONE JSON object and nothing else.

Input items: {items}
For each item translate "src" into every language listed in its "langs" and reply as
{{"<id>": {{"<lang>": "<translation>", ...}}, ...}}.

Language codes: {langs}
Rules:
- Faithful: add no facts, remove no facts, no marketing tone of your own. If the source is already in a target language, keep it as is.
- Keep project names, product names, links, code, @handles, numbers, versions, emoji and punctuation such as a trailing "…" exactly as in the source. Keep HTML entities like &amp; unchanged.
- One line per translation, no markdown, no notes.
- {glossary}
"""

HOOK_PROMPT = """You write the ONE-LINE hook shown in the rows of a GitHub trending table. Reply with ONE JSON object and nothing else.

Input items: {items}
For each item write a hook in every language listed in its "langs" and reply as
{{"<id>": {{"<lang>": "<hook>", ...}}, ...}}.
The facts come only from "src". The long text stays elsewhere, so leave details out of the hook instead of squeezing them in.

Language codes: {langs}
{rule}
- Items with "literal": true look cracked / pirated / pre-activated: write a flat, literal label, nothing that sells it.
- Keep names and numbers exactly as in the source when you use them. Traditional Chinese uses Taiwan/Hong Kong wording.
- {glossary}
"""

POLISH_PROMPT = """You are a copy editor for a GitHub trending list. Rewrite each text below in the language named by its "lang".
Reply with ONE JSON object {{"<id>": "<rewritten text>", ...}} and nothing else.

Voice: plain spoken words, like a short-video host: lead with the point in the first words, then one sentence that says what it does and why it is worth a look. Condensed and eye-catching, but never clickbait, never exaggerated, never invented.
Hard rules:
- Keep every fact in the text; add no fact, number, name or claim that is not already there. You may cut filler words, not facts.
- Keep project names, product names, links, code, @handles, numbers, versions and emoji exactly as written. Keep a trailing "…" or "：" if the text has one.
- Stay in the same language (and for Traditional Chinese use Taiwan/Hong Kong wording). No exclamation marks, no hype words (e.g. 炸裂, 颠覆, 震惊, game-changer, revolutionary, insane).
- Not longer than the original plus a few characters. One line, no markdown, no quotes around it.
- These texts are the detailed intro of a project. The ranking tables show a separate one-line hook (stage "hooks"), so keep the details here; never cut a text down to a hook.
- {glossary}

Items: {items}
"""

# hype / clickbait words that make a polished text be rejected
HYPE = re.compile(
    r"炸裂|颠覆|顛覆|震惊|震驚|史诗|史詩|封神|吊打|吊打|逆天|神器|重磅|必看|绝绝子|絕絕子|"
    r"game[- ]?changer|revolutionary|mind[- ]?blowing|insane|you won't believe|ヤバい|衝撃|革命的|충격|혁명적",
    re.I)
_URL = re.compile(r"https?://\S+")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9_.+#\-/@]*[A-Za-z0-9+#]|[A-Za-z]")
_SENT_END = re.compile(r"[.!?:;。！？：；—/|]\s*$")
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


class Runner(Protocol):
    def ask(self, prompt: str) -> str: ...


# ----------------------------------------------------------------------------- guards

def _norm_nums(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in _NUM.findall(_URL.sub(" ", text))}


def _protected_tokens(text: str, lang: str) -> set[str]:
    """Names/identifiers that must survive a rewrite (lower-cased).

    For non-English text every Latin word counts. For English only identifier-like words
    (digits, inner capitals, symbols), all-caps words and capitalised words that do not start a sentence.
    """
    toks: set[str] = set()
    for m in _LATIN.finditer(_URL.sub(" ", text)):
        w = m.group(0)
        if len(w) < 2:
            continue
        if lang != "en":
            toks.add(w.lower())
            continue
        before = text[:m.start()]
        starts_sentence = not before.strip() or bool(_SENT_END.search(before))
        identifier = bool(re.search(r"[0-9_.+#\-/@]", w)) or any(c.isupper() for c in w[1:])
        capitalised = w[0].isupper() and not starts_sentence
        if identifier or capitalised:
            toks.add(w.lower())
    return toks


def _identifier_tokens(text: str) -> set[str]:
    """Latin words that look like names/identifiers (digits, symbols, inner capitals), lower-cased."""
    out = set()
    for m in _LATIN.finditer(_URL.sub(" ", text)):
        w = m.group(0)
        if len(w) >= 2 and (re.search(r"[0-9_.+#@]", w) or any(any(c.isupper() for c in seg[1:]) and any(c.islower() for c in seg) for seg in w.split("-"))):
            out.add(w.lower())
    return out


def _contains_token(text_l: str, tok: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(tok) + r"(?![a-z])", text_l) is not None


def check_translation(src: str, out: Any) -> str | None:
    """None if `out` is an acceptable translation of `src`, else the reason it is not."""
    if not isinstance(out, str) or not out.strip():
        return "empty"
    if "\n" in out or "```" in out:
        return "not a single plain line"
    if len(out) > len(src) * 8 + 40:
        return "implausibly long"
    # A small number may legitimately turn into a word (one -> 1 つ, 64 -> 六十四), anything else may not.
    src_n, out_n = _norm_nums(src), _norm_nums(out)
    missing = {n for n in src_n - out_n if len(n) >= 2}
    if missing and not re.search("[一二三四五六七八九十百千万萬]", out):
        return f"number {sorted(missing)[0]} from the source is missing"
    if {n for n in out_n - src_n if len(n) >= 2}:
        return "a number not in the source was added"
    low = out.lower()
    for tok in _identifier_tokens(src):  # product names, versions, acronyms with symbols/inner capitals
        if not any(_contains_token(low, t) for t in {tok, tok.rstrip("s")}):
            return f"name/term {tok!r} from the source is missing"
    return None


def check_polished(src: str, out: Any, lang: str) -> str | None:
    """None if `out` is a safe polish of `src` (same facts, no hype), else the reason it is rejected."""
    if not isinstance(out, str) or not out.strip():
        return "empty"
    out = out.strip()
    if "\n" in out or "```" in out:
        return "not a single plain line"
    if len(out) > max(len(src) * 1.3, len(src) + 20):
        return "longer than the original"
    if len(out) < len(src) * 0.35:
        return "drops too much of the original"
    if _norm_nums(src) != _norm_nums(out):
        return "numbers differ from the original"
    if re.search(r"[!！]", out) and not re.search(r"[!！]", src):
        return "exclamation mark added"
    if HYPE.search(out) and not HYPE.search(src):
        return "hype wording"
    src_toks, out_toks = _protected_tokens(src, lang), _protected_tokens(out, lang)
    lost = [t for t in src_toks if not _contains_token(out.lower(), t)]
    if lost:
        return f"name/term {lost[0]!r} lost"
    if lang != "en":
        added = [t for t in _identifier_tokens(out) - _identifier_tokens(src)]
        if added:
            return f"new term {added[0]!r} added"
    for a, b in (("…", "…"), ("：", "：")):
        if src.rstrip().endswith(a) and not out.endswith(b):
            return f"lost the trailing {a!r}"
    return None


# ----------------------------------------------------------------------------- state

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if path.exists():
        st = json.loads(path.read_text("utf-8"))
    else:
        st = {}
    st.setdefault("_comment", "Which texts tools/i18n_pipeline.py has already polished. key = kind|name|lang; "
                              "sha = hash of the text as it is now. Safe to delete: everything is polished again.")
    st.setdefault("items", {})
    return st


def save_state(st: dict[str, Any], path: Path = STATE_PATH) -> None:
    st["items"] = dict(sorted(st["items"].items()))
    path.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", "utf-8")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")


# ----------------------------------------------------------------------------- collecting work

def displayed_newcomers(new: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The new-repo items the READMEs actually show (top N of each category), in ranking order."""
    items: list[dict[str, Any]] = []
    if not new or not new.get("ok"):
        return items
    if "categories" in new:
        for block in (new.get("categories") or {}).values():
            if block.get("ok"):
                items.extend((block.get("items") or [])[:TOP_N])
    else:
        items = (new.get("items") or [])[:TOP_N]
    seen, out = set(), []
    for it in items:
        if it["name"] not in seen:
            seen.add(it["name"])
            out.append(it)
    return out


def translation_gaps(lib: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """[{id, src, langs}] for descriptions whose current text (repo + source hash) lacks languages in the library."""
    gaps = []
    for it in items:
        desc = (it.get("description") or "").strip()
        if not desc:
            continue
        langs = nci.missing_langs(lib, it["name"], it["description"])
        if langs:
            gaps.append({"id": it["name"], "src": it["description"], "langs": langs})
    return gaps


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


class Budget:
    def __init__(self, seconds: float, clock: Callable[[], float] = time.monotonic):
        self._clock, self._end = clock, clock() + seconds

    def left(self) -> bool:
        return self._clock() < self._end


# ----------------------------------------------------------------------------- stage 1: translate

def translate(root: Path, items: list[dict[str, Any]], runner: Runner, budget: Budget,
              log: Callable[[str], None] = print, limit: int | None = None, dry_run: bool = False,
              today: str | None = None) -> dict[str, int]:
    """Fill the translation library for the ranked descriptions. A hit (same repo + source hash) costs nothing."""
    path = root / LIB_REL
    lib = nci.load(path)
    today = today or dt.date.today().isoformat()
    hs = nci.hit_stats(lib, items)
    gaps = translation_gaps(lib, items)
    _log_library(hs, len(gaps), log)
    touched = False
    for it in items:  # entries that were used today stay alive for --prune-days
        if it.get("description") and not nci.missing_langs(lib, it["name"], it["description"]):
            touched |= nci.touch(lib, it["name"], it["description"], today)
    if touched and not dry_run:
        nci.save(lib, path)
    if limit is not None:
        gaps = gaps[:limit]
    stat = {"total": hs["total"], "hits": hs["hits"], "partial": hs["partial"], "new": hs["new"],
            "todo": len(gaps), "translated": 0, "rejected": 0, "errors": 0, "calls": 0}
    if dry_run or not gaps:
        return stat
    glossary = load_glossary(root)
    streak = 0
    for batch in _chunks(gaps, BATCH):
        if not budget.left():
            log("translate: time budget used up; the rest waits for the next run")
            break
        glos = glossary_for([g["src"] for g in batch], sorted({l for g in batch for l in g["langs"]}), glossary)
        prompt = TRANSLATE_PROMPT.format(items=json.dumps(batch, ensure_ascii=False),
                                         langs=", ".join(LANGS), glossary=glos)
        try:
            stat["calls"] += 1
            reply = llm.extract_json(runner.ask(prompt))
            streak = 0
        except llm.LLMError as e:
            stat["errors"] += 1
            streak += 1
            log(f"translate: call failed ({e}); keeping the original text for {len(batch)} repo(s)")
            if streak >= MAX_CONSECUTIVE_ERRORS:
                log("translate: too many failures in a row; stopping this stage")
                break
            continue
        for g in batch:
            got = reply.get(g["id"])
            if not isinstance(got, dict):
                stat["rejected"] += 1
                continue
            for lang in g["langs"]:
                bad = check_translation(g["src"], got.get(lang))
                if bad:
                    log(f"translate: {g['id']} [{lang}] rejected: {bad}")
                else:
                    nci.put(lib, g["id"], g["src"], lang, got[lang].strip(), today)
            if nci.missing_langs(lib, g["id"], g["src"]):
                stat["rejected"] += 1
            else:
                stat["translated"] += 1
        nci.save(lib, path)  # save after every batch so a later failure loses nothing
    return stat


def _log_library(hs: dict[str, int], to_send: int, log: Callable[[str], None]) -> None:
    log(f"translate: library {hs['hits']}/{hs['total']} hits ({_pct(hs['hits'], hs['total'])}), "
        f"{hs['partial']} partial, {hs['new']} new -> {to_send} to send to the model, 0 calls for the hits")


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "n/a"


# ----------------------------------------------------------------------------- stage 2: hooks

def _hook_langs_missing(stored: dict[str, str] | None, detail: str) -> list[str]:
    """Languages whose hook is absent or breaks the length/hype rules (so it is written again)."""
    stored = stored or {}
    return [l for l in LANGS if hooks.check_hook(stored.get(l), l, detail)]


def _detail_blob(entry: dict[str, Any] | None, src: str) -> str:
    """Every text a hook may take a number from: the source and all stored translations."""
    entry = entry or {}
    return " ".join([src] + [str(entry.get(l, "")) for l in LANGS])


def hook_gaps(root: Path, items: list[dict[str, Any]], targets: tuple[str, ...] = ("newcomers", "projects")
              ) -> list[dict[str, Any]]:
    """[{id, src, langs, kind, ...}]: texts that still need a hook, newcomers first (the ranking order)."""
    gaps: list[dict[str, Any]] = []
    if "newcomers" in targets:
        lib = nci.load(root / LIB_REL)
        for it in items:
            desc = (it.get("description") or "").strip()
            if not desc:
                continue
            entry = nci.lookup(lib, it["name"], it["description"])
            langs = _hook_langs_missing((entry or {}).get("hook"), _detail_blob(entry, it["description"]))
            if langs:
                gap = {"id": it["name"], "src": it["description"], "langs": langs, "kind": "newcomer"}
                if it.get("suspicious"):
                    gap["literal"] = True
                gaps.append(gap)
    if "projects" in targets:
        for p in json.loads((root / "data/projects.json").read_text("utf-8")):
            detail = " ".join((p.get("desc") or {}).values())
            langs = _hook_langs_missing(p.get("hook"), detail)
            if langs:
                gaps.append({"id": p["name"], "src": (p.get("desc") or {}).get("en", ""), "langs": langs,
                             "kind": "project"})
    return gaps


def write_hooks(root: Path, items: list[dict[str, Any]], runner: Runner, budget: Budget,
                log: Callable[[str], None] = print, limit: int | None = None, dry_run: bool = False,
                targets: tuple[str, ...] = ("newcomers", "projects"), today: str | None = None) -> dict[str, int]:
    """Write the one-line hooks that are missing. Only the `hook` field is touched: descriptions and
    translations (also those already in the library) are never changed or sent to the model again."""
    today = today or dt.date.today().isoformat()
    gaps = hook_gaps(root, items, targets)
    if limit is not None:
        gaps = gaps[:limit]
    stat = {"todo": len(gaps), "written": 0, "rejected": 0, "errors": 0, "calls": 0}
    log(f"hooks: {len(gaps)} text(s) without a valid one-line hook")
    if dry_run or not gaps:
        return stat
    glossary = load_glossary(root)
    streak = 0
    for batch in _chunks(gaps, BATCH):
        if not budget.left():
            log("hooks: time budget used up; the rest waits for the next run")
            break
        payload = [{k: v for k, v in g.items() if k != "kind"} for g in batch]
        glos = glossary_for([g["src"] for g in batch], sorted({l for g in batch for l in g["langs"]}), glossary)
        prompt = HOOK_PROMPT.format(items=json.dumps(payload, ensure_ascii=False), langs=", ".join(LANGS),
                                    rule=hooks.HOOK_RULE, glossary=glos)
        try:
            stat["calls"] += 1
            reply = llm.extract_json(runner.ask(prompt))
            streak = 0
        except llm.LLMError as e:
            stat["errors"] += 1
            streak += 1
            log(f"hooks: call failed ({e}); keeping what exists for {len(batch)} text(s)")
            if streak >= MAX_CONSECUTIVE_ERRORS:
                log("hooks: too many failures in a row; stopping this stage")
                break
            continue
        lib = nci.load(root / LIB_REL)
        projects_path = root / "data/projects.json"
        projects = json.loads(projects_path.read_text("utf-8"))
        by_name = {p["name"]: p for p in projects}
        for g in batch:
            got = reply.get(g["id"])
            if not isinstance(got, dict):
                stat["rejected"] += 1
                continue
            if g["kind"] == "newcomer":
                detail = _detail_blob(nci.lookup(lib, g["id"], g["src"]), g["src"])
            else:
                detail = " ".join((by_name[g["id"]].get("desc") or {}).values())
            for lang in g["langs"]:
                text = got.get(lang)
                bad = hooks.check_hook(text, lang, detail)
                if bad:
                    log(f"hooks: {g['id']} [{lang}] rejected: {bad}")
                    stat["rejected"] += 1
                    continue
                if g["kind"] == "newcomer":
                    nci.put_hook(lib, g["id"], g["src"], lang, text.strip(), today)
                else:
                    by_name[g["id"]].setdefault("hook", {})[lang] = text.strip()
                stat["written"] += 1
        nci.save(lib, root / LIB_REL)  # saved after every batch so a later failure loses nothing
        _write_json(projects_path, projects)
    return stat


# ----------------------------------------------------------------------------- stage 3: polish

def _polish_jobs(root: Path, items: list[dict[str, Any]], targets: tuple[str, ...],
                 state: dict[str, Any], counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    """Texts that still need polishing: {key, kind, name, lang, text}. `counts` gets candidates/skipped."""
    jobs: list[dict[str, Any]] = []
    counts = counts if counts is not None else {}
    counts.update(candidates=0, skipped=0)
    done = state["items"]

    def add(kind: str, name: str, lang: str, text: str, extra: dict[str, Any] | None = None) -> None:
        key = f"{kind}|{name}|{lang}"
        if not text.strip():
            return
        counts["candidates"] += 1
        rec = done.get(key)
        if rec and rec.get("sha") == sha(text) and rec.get("v") == POLISH_VERSION:
            if rec.get("ok") or rec.get("fails", 0) >= MAX_FAILS:
                counts["skipped"] += 1
                return
        if text.strip():
            jobs.append({"key": key, "kind": kind, "name": name, "lang": lang, "text": text, **(extra or {})})

    if "newcomers" in targets:
        lib = nci.load(root / LIB_REL)
        for it in items:
            if it.get("suspicious") or not it.get("description"):
                continue  # suspected cracked/pirated repos stay literal; polish must not make them sound better
            entry = nci.lookup(lib, it["name"], it["description"])
            if not entry:
                continue
            for lang in LANGS:
                if entry.get(lang, "").strip():
                    # keyed by repo + source hash + language: a changed source is a new, unpolished entry
                    add("newcomer", f"{it['name']}@{nci.src_hash(it['description'])}", lang, entry[lang],
                        {"repo": it["name"], "src": it["description"]})
    if "projects" in targets:
        for p in json.loads((root / "data/projects.json").read_text("utf-8")):
            for lang in LANGS:
                add("project", p["name"], lang, (p.get("desc") or {}).get(lang, ""))
    if "categories" in targets:
        for c in json.loads((root / "data/categories.json").read_text("utf-8")):
            for lang in LANGS:
                add("category", c["id"], lang, (c.get("desc") or {}).get(lang, ""))
    return jobs


def _apply(root: Path, accepted: list[dict[str, Any]]) -> None:
    """Write accepted polished texts back to the file each came from."""
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for a in accepted:
        by_kind.setdefault(a["kind"], []).append(a)
    if "newcomer" in by_kind:
        path = root / LIB_REL
        lib = nci.load(path)
        for a in by_kind["newcomer"]:
            nci.put(lib, a["repo"], a["src"], a["lang"], a["new"])
        nci.save(lib, path)
    for kind, fname, key in (("project", "data/projects.json", "name"), ("category", "data/categories.json", "id")):
        if kind in by_kind:
            path = root / fname
            rows = json.loads(path.read_text("utf-8"))
            index = {r[key]: r for r in rows}
            for a in by_kind[kind]:
                index[a["name"]]["desc"][a["lang"]] = a["new"]
            _write_json(path, rows)


def polish(root: Path, items: list[dict[str, Any]], runner: Runner, budget: Budget,
           targets: tuple[str, ...] = DEFAULT_TARGETS, log: Callable[[str], None] = print,
           limit: int | None = None, dry_run: bool = False) -> dict[str, int]:
    state = load_state(root / "data/polish_state.json")
    glossary = load_glossary(root)
    counts: dict[str, int] = {}
    jobs = _polish_jobs(root, items, targets, state, counts)
    log(f"polish: {counts['skipped']}/{counts['candidates']} texts already polished or given up on (skipped), "
        f"{len(jobs)} to send to the model")
    if limit is not None:
        jobs = jobs[:limit]
    stat = {"todo": len(jobs), "polished": 0, "unchanged": 0, "rejected": 0, "errors": 0,
            "skipped": counts["skipped"], "candidates": counts["candidates"]}
    if dry_run or not jobs:
        return stat
    # group by language so each prompt is one language; small batches keep replies reliable
    by_lang: dict[str, list[dict[str, Any]]] = {}
    for j in jobs:
        by_lang.setdefault(j["lang"], []).append(j)
    streak = 0
    stop = False
    for lang, group in by_lang.items():
        for batch in _chunks(group, BATCH):
            if stop or not budget.left():
                log("polish: stopping (time budget or repeated failures); the rest waits for the next run")
                stop = True
                break
            payload = [{"id": str(i), "lang": LANG_NAMES[lang], "text": j["text"]} for i, j in enumerate(batch)]
            prompt = POLISH_PROMPT.format(items=json.dumps(payload, ensure_ascii=False),
                                          glossary=glossary_for([j["text"] for j in batch], [lang], glossary))
            try:
                reply = llm.extract_json(runner.ask(prompt))
                streak = 0
            except llm.LLMError as e:
                stat["errors"] += 1
                streak += 1
                log(f"polish: call failed ({e}); keeping the existing text for {len(batch)} item(s)")
                if streak >= MAX_CONSECUTIVE_ERRORS:
                    stop = True
                continue
            accepted = []
            for i, j in enumerate(batch):
                new = reply.get(str(i))
                bad = check_polished(j["text"], new, lang)
                rec = state["items"].get(j["key"])
                fails = (rec or {}).get("fails", 0) if rec and rec.get("sha") == sha(j["text"]) else 0
                if bad:
                    log(f"polish: {j['key']} rejected ({bad}); raw text kept")
                    stat["rejected"] += 1
                    state["items"][j["key"]] = {"sha": sha(j["text"]), "v": POLISH_VERSION, "ok": False,
                                                "fails": fails + 1}
                    continue
                new = new.strip()
                if new == j["text"]:
                    stat["unchanged"] += 1
                else:
                    accepted.append({**j, "new": new})
                    stat["polished"] += 1
                state["items"][j["key"]] = {"sha": sha(new), "v": POLISH_VERSION, "ok": True}
            if accepted:
                _apply(root, accepted)
            save_state(state, root / "data/polish_state.json")
    save_state(state, root / "data/polish_state.json")
    return stat


# ----------------------------------------------------------------------------- orchestration

def run(root: Path, new: dict[str, Any] | None, *, do_translate: bool = True, do_hooks: bool = True, do_polish: bool = True,
        targets: tuple[str, ...] = DEFAULT_TARGETS, env: dict[str, str] | None = None,
        make_runner: Callable[[str, str], Any] | None = None, budget_sec: float | None = None,
        log: Callable[[str], None] = print, limit: int | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Run the stages. Raises nothing for LLM/model problems; those stages are skipped and reported."""
    env = dict(os.environ if env is None else env)
    make_runner = make_runner or (lambda backend, model: llm.make_agent(backend, model, env=env))
    budget = Budget(budget_sec if budget_sec is not None else float(env.get("I18N_BUDGET_SEC", DEFAULT_BUDGET_SEC)))
    items = displayed_newcomers(new)
    result: dict[str, Any] = {}
    polish_model = env.get("POLISH_MODEL") or llm.DEFAULT_MODEL
    translate_model = env.get("I18N_TRANSLATE_MODEL") or polish_model
    translate_backend = env.get("I18N_TRANSLATE_BACKEND") or "cursor"   # CI: Cursor CLI + CURSOR_API_KEY
    polish_backend = env.get("I18N_POLISH_BACKEND") or "agy"            # owner's machine: Antigravity CLI
    hook_backend = env.get("I18N_HOOK_BACKEND") or translate_backend
    runners: dict[tuple[str, str], Any] = {}

    def ready(backend: str, model: str) -> Any | None:
        if (backend, model) not in runners:
            r = make_runner(backend, model)
            why = r.unavailable_reason()
            runners[(backend, model)] = None if why else r
            if why:
                log(f"i18n: {backend} / {model}: skipped, {why}")
        return runners[(backend, model)]

    if do_translate:
        lib = nci.load(root / LIB_REL)
        gaps = translation_gaps(lib, items)
        if not gaps:
            hs = nci.hit_stats(lib, items)
            result["translate"] = {"todo": 0, **hs, "calls": 0}
            log(f"translate: library {hs['hits']}/{hs['total']} hits ({_pct(hs['hits'], hs['total'])}), "
                "nothing new, 0 model calls")
        elif dry_run:
            result["translate"] = {"todo": len(gaps)}
            _log_library(nci.hit_stats(lib, items), len(gaps), log)
        elif (r := ready(translate_backend, translate_model)) is None:
            result["translate"] = {"todo": len(gaps), "skipped": True}
            _log_library(nci.hit_stats(lib, items), len(gaps), log)
        else:
            result["translate"] = translate(root, items, r, budget, log, limit)
            log(f"translate: {result['translate']}")
    if do_hooks:
        gaps = hook_gaps(root, items)
        if not gaps:
            result["hooks"] = {"todo": 0}
            log("hooks: every text already has a valid one-line hook, 0 model calls")
        elif dry_run:
            result["hooks"] = {"todo": len(gaps)}
            log(f"hooks: {len(gaps)} text(s) without a valid one-line hook (dry run)")
        elif (r := ready(hook_backend, translate_model)) is None:
            result["hooks"] = {"todo": len(gaps), "skipped": True}
        else:
            result["hooks"] = write_hooks(root, items, r, budget, log, limit)
            log(f"hooks: {result['hooks']}")
    if do_polish:
        jobs = _polish_jobs(root, items, targets, load_state(root / "data/polish_state.json"))
        if not jobs:
            result["polish"] = {"todo": 0}
            log("polish: nothing to do, every text is already polished")
        elif dry_run:
            result["polish"] = {"todo": len(jobs)}
        elif (r := ready(polish_backend, polish_model)) is None:
            result["polish"] = {"todo": len(jobs), "skipped": True}
        else:
            result["polish"] = polish(root, items, r, budget, targets, log, limit)
            log(f"polish: {result['polish']}")
    return result


def run_safe(root: Path, new: dict[str, Any] | None, **kw: Any) -> dict[str, Any]:
    """`run`, but any unexpected error is logged and swallowed: the scheduled update must go on."""
    log = kw.get("log", print)
    try:
        return run(root, new, **kw)
    except Exception as e:  # noqa: BLE001 - deliberately broad, see docstring
        log(f"i18n: pipeline error ignored ({type(e).__name__}: {e}); existing texts kept")
        return {"error": f"{type(e).__name__}: {e}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--translate", action="store_true", help="only the translate stage")
    ap.add_argument("--hooks", action="store_true", help="only the one-line hook stage")
    ap.add_argument("--polish", action="store_true", help="only the polish stage")
    ap.add_argument("--targets", default=",".join(DEFAULT_TARGETS),
                    help="what to polish: newcomers,projects,categories (default: newcomers,projects)")
    ap.add_argument("--limit", type=int, help="process at most N texts per stage")
    ap.add_argument("--dry-run", action="store_true", help="count the work, change nothing, call nothing")
    args = ap.parse_args(argv)
    both = not (args.translate or args.hooks or args.polish)
    stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))
    res = run_safe(ROOT, stats.get("newcomers"), do_translate=both or args.translate,
                   do_hooks=both or args.hooks, do_polish=both or args.polish, targets=tuple(t for t in args.targets.split(",") if t),
                   limit=args.limit, dry_run=args.dry_run)
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
