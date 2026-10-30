#!/usr/bin/env python3
"""Translate new-repo descriptions and polish all copy, as part of the scheduled update.

Two stages, both optional and both fail-safe (any problem leaves the existing text in place and
never fails the update):

1. translate  every description in the new-repos ranking that has no current translation
              (data/newcomer_i18n.json, keyed by repo; `src` must match the live description, so
              anything already translated is skipped) -> zh-Hans, zh-Hant, ja, ko (+ en if the source
              contains CJK text).
2. polish     rewrite the project blurbs (data/projects.json), the translated new-repo descriptions
              and, only on request, the category descriptions in a short, plain, lead-with-the-point
              voice. Each text is polished once: data/polish_state.json remembers the hash of the text
              that was polished, so unchanged text is never sent again. A polished text is accepted
              only if it passes the guards in `check_polished`; otherwise the previous text stays.

Both stages call an agent CLI through tools/llm.py, model gemini-3.8-flash-medium by default
(POLISH_MODEL / I18N_TRANSLATE_MODEL):
  translate  backend I18N_TRANSLATE_BACKEND, default "cursor" (Cursor CLI, key CURSOR_API_KEY: the CI step)
  polish     backend I18N_POLISH_BACKEND,    default "agy"    (Antigravity CLI on the owner's machine)
Without the CLI / sign-in / key, or when the model is not offered, the stage is skipped with a message.
CI runs translate only; polish is run locally (tools/polish_local.sh, or tools/local_daily.sh).

Usage: python3 tools/i18n_pipeline.py [--translate] [--polish] [--targets newcomers,projects,categories]
                                      [--limit N] [--dry-run]
       (no stage flag = both stages)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Protocol

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402
import newcomer_i18n as nci  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data/polish_state.json"
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
GLOSSARY = (
    "Fixed terms: star = 星标 (zh-Hans) / 星號 (zh-Hant); stars per day = 星标/天; "
    "agent = 智能体 (zh-Hans) / 代理 (zh-Hant) / エージェント (ja) / 에이전트 (ko). "
    "Product, repo, company and model names stay exactly as written."
)

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

POLISH_PROMPT = """You are a copy editor for a GitHub trending list. Rewrite each text below in the language named by its "lang".
Reply with ONE JSON object {{"<id>": "<rewritten text>", ...}} and nothing else.

Voice: plain spoken words, like a short-video host: lead with the point in the first words, then one sentence that says what it does and why it is worth a look. Condensed and eye-catching, but never clickbait, never exaggerated, never invented.
Hard rules:
- Keep every fact in the text; add no fact, number, name or claim that is not already there. You may cut filler words, not facts.
- Keep project names, product names, links, code, @handles, numbers, versions and emoji exactly as written. Keep a trailing "…" or "：" if the text has one.
- Stay in the same language (and for Traditional Chinese use Taiwan/Hong Kong wording). No exclamation marks, no hype words (e.g. 炸裂, 颠覆, 震惊, game-changer, revolutionary, insane).
- Not longer than the original plus a few characters. One line, no markdown, no quotes around it.
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


def translation_gaps(cache: dict[str, dict[str, str]], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """[{id, src, langs}] for descriptions with no current translation, only the languages that lack one."""
    gaps = []
    for it in items:
        desc = (it.get("description") or "").strip()
        if not desc:
            continue
        entry = cache.get(it["name"])
        have = entry if entry and entry.get("src") == it.get("description") else {}
        langs = [l for l in nci.required_langs(it["description"]) if not have.get(l, "").strip()]
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
              log: Callable[[str], None] = print, limit: int | None = None, dry_run: bool = False) -> dict[str, int]:
    path = root / "data/newcomer_i18n.json"
    cache = nci.load(path)
    gaps = translation_gaps(cache, items)
    if limit is not None:
        gaps = gaps[:limit]
    stat = {"todo": len(gaps), "translated": 0, "rejected": 0, "errors": 0}
    if dry_run or not gaps:
        return stat
    streak = 0
    for batch in _chunks(gaps, BATCH):
        if not budget.left():
            log("translate: time budget used up; the rest waits for the next run")
            break
        prompt = TRANSLATE_PROMPT.format(items=json.dumps(batch, ensure_ascii=False),
                                         langs=", ".join(LANGS), glossary=GLOSSARY)
        try:
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
            entry = cache.get(g["id"])
            entry = dict(entry) if entry and entry.get("src") == g["src"] else {"src": g["src"]}
            ok = True
            for lang in g["langs"]:
                bad = check_translation(g["src"], got.get(lang))
                if bad:
                    log(f"translate: {g['id']} [{lang}] rejected: {bad}")
                    ok = False
                else:
                    entry[lang] = got[lang].strip()
            if all(entry.get(l, "").strip() for l in nci.required_langs(g["src"])):
                stat["translated"] += 1
            else:
                stat["rejected"] += 1
            if len(entry) > 1:
                cache[g["id"]] = entry
        _write_json(path, cache)  # save after every batch so a later failure loses nothing
    return stat


# ----------------------------------------------------------------------------- stage 2: polish

def _polish_jobs(root: Path, items: list[dict[str, Any]], targets: tuple[str, ...],
                 state: dict[str, Any]) -> list[dict[str, Any]]:
    """Texts that still need polishing: {key, kind, name, lang, text}."""
    jobs: list[dict[str, Any]] = []
    done = state["items"]

    def add(kind: str, name: str, lang: str, text: str) -> None:
        key = f"{kind}|{name}|{lang}"
        rec = done.get(key)
        if rec and rec.get("sha") == sha(text) and rec.get("v") == POLISH_VERSION:
            if rec.get("ok") or rec.get("fails", 0) >= MAX_FAILS:
                return
        if text.strip():
            jobs.append({"key": key, "kind": kind, "name": name, "lang": lang, "text": text})

    if "newcomers" in targets:
        cache = nci.load(root / "data/newcomer_i18n.json")
        for it in items:
            if it.get("suspicious"):
                continue  # suspected cracked/pirated repos stay literal; polish must not make them sound better
            entry = cache.get(it["name"])
            if not entry or entry.get("src") != it.get("description"):
                continue
            for lang in LANGS:
                if entry.get(lang, "").strip():
                    add("newcomer", it["name"], lang, entry[lang])
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
        path = root / "data/newcomer_i18n.json"
        cache = nci.load(path)
        for a in by_kind["newcomer"]:
            cache[a["name"]][a["lang"]] = a["new"]
        _write_json(path, cache)
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
    jobs = _polish_jobs(root, items, targets, state)
    if limit is not None:
        jobs = jobs[:limit]
    stat = {"todo": len(jobs), "polished": 0, "unchanged": 0, "rejected": 0, "errors": 0}
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
            prompt = POLISH_PROMPT.format(items=json.dumps(payload, ensure_ascii=False), glossary=GLOSSARY)
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

def run(root: Path, new: dict[str, Any] | None, *, do_translate: bool = True, do_polish: bool = True,
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
        gaps = translation_gaps(nci.load(root / "data/newcomer_i18n.json"), items)
        if not gaps:
            result["translate"] = {"todo": 0}
            log("translate: nothing to do, every displayed description already has a current translation")
        elif dry_run:
            result["translate"] = {"todo": len(gaps)}
        elif (r := ready(translate_backend, translate_model)) is None:
            result["translate"] = {"todo": len(gaps), "skipped": True}
        else:
            result["translate"] = translate(root, items, r, budget, log, limit)
            log(f"translate: {result['translate']}")
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
    ap.add_argument("--polish", action="store_true", help="only the polish stage")
    ap.add_argument("--targets", default=",".join(DEFAULT_TARGETS),
                    help="what to polish: newcomers,projects,categories (default: newcomers,projects)")
    ap.add_argument("--limit", type=int, help="process at most N texts per stage")
    ap.add_argument("--dry-run", action="store_true", help="count the work, change nothing, call nothing")
    args = ap.parse_args(argv)
    both = not (args.translate or args.polish)
    stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))
    res = run_safe(ROOT, stats.get("newcomers"), do_translate=both or args.translate,
                   do_polish=both or args.polish, targets=tuple(t for t in args.targets.split(",") if t),
                   limit=args.limit, dry_run=args.dry_run)
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
