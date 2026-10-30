"""Translate + polish pipeline: no network, no real Cursor CLI (a fake runner stands in)."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import i18n_pipeline as pipe  # noqa: E402
import llm  # noqa: E402
import update_stars as up  # noqa: E402

LANG5 = ("en", "zh-Hans", "zh-Hant", "ja", "ko")


class FakeRunner:
    """Answers translate/polish prompts from a callback; counts calls."""

    def __init__(self, translate=None, polish=None, error=None):
        self.calls, self.translate, self.polish, self.error = [], translate, polish, error

    def ask(self, prompt):
        self.calls.append(prompt)
        if self.error:
            raise llm.LLMError(self.error)
        if prompt.startswith("You translate"):
            items = json.loads(prompt.split("Input items: ", 1)[1].split("\nFor each item", 1)[0])
            return json.dumps({i["id"]: self.translate(i) for i in items}, ensure_ascii=False)
        items = json.loads(prompt.split("Items: ", 1)[1])
        return "```json\n" + json.dumps({i["id"]: self.polish(i["text"]) for i in items}, ensure_ascii=False) + "\n```"


class Ready:
    def __init__(self, runner, why=None):
        self.runner, self.why = runner, why

    def unavailable_reason(self):
        return self.why

    def ask(self, prompt):
        return self.runner.ask(prompt)


def fake_tr(item):
    return {l: f"[{l}] {item['src']}" for l in item["langs"]}


class Repo:
    """A throwaway repo root with the data files the pipeline reads and writes."""

    def __init__(self, descs, cache=None, projects=None, suspicious=()):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir()
        self.items = [{"name": n, "description": d, "suspicious": n in suspicious} for n, d in descs.items()]
        self.new = {"ok": True, "categories": {"ai": {"ok": True, "items": self.items}}}
        self.write("newcomer_i18n.json", cache or {})
        self.write("projects.json", projects or [])
        self.write("categories.json", [{"id": "ai", "desc": {l: f"cat {l}" for l in LANG5}}])

    def write(self, name, data):
        (self.root / "data" / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")

    def read(self, name):
        return json.loads((self.root / "data" / name).read_text("utf-8"))

    def close(self):
        self.tmp.cleanup()


ZH = "一个用 Ghidra 做 3 件事的工具。"


def project(name, text_en, text_other=ZH):
    desc = {l: text_other for l in LANG5}
    desc["en"] = text_en
    return {"name": name, "url": f"https://github.com/{name}", "category": "ai", "desc": desc}


def short(t):
    return t.replace("A tool that does", "Does").replace(ZH, "用 Ghidra 做 3 件事。")


class GuardTests(unittest.TestCase):
    def test_polish_accepts_same_facts_shorter(self):
        src = "Reverse engineers stare at assembly for days; this hooks into Ghidra so an unreadable binary gets explained in one sentence."
        out = "Ghidra plus AI: it explains an unreadable binary in one sentence instead of days of assembly."
        self.assertIsNone(pipe.check_polished(src, out, "en"))

    def test_polish_rejects_changed_numbers_names_and_hype(self):
        src = "用一张照片生成 AI 数字人口播视频：Renoise MCP 生成 + 5 种剪辑风格 + 48 个包装组件。"
        cases = {
            "numbers": "一张照片出 AI 数字人口播：Renoise MCP 生成，6 种剪辑风格，48 个包装组件。",
            "name lost": "一张照片出 AI 数字人口播：MCP 生成，5 种剪辑风格，48 个包装组件。",
            "new term": "一张照片出 AI 数字人口播：Renoise MCP 加 Sora2 生成，5 种剪辑风格，48 个包装组件。",
            "hype": "一张照片出 AI 数字人口播，炸裂！Renoise MCP 生成，5 种剪辑风格，48 个包装组件。",
            "bang": "一张照片出 AI 数字人口播！Renoise MCP 生成，5 种剪辑风格，48 个包装组件。",
            "empty": "",
            "multiline": "一张照片出数字人口播\nRenoise MCP 生成，5 种，48 个",
            "too long": src + "，" + "非常好用" * 20,
        }
        for label, out in cases.items():
            with self.subTest(label):
                self.assertIsNotNone(pipe.check_polished(src, out, "zh-Hans"))
        self.assertIsNone(pipe.check_polished(src, "一张照片出 AI 数字人口播：Renoise MCP 生成，5 种剪辑风格，48 个包装组件。", "zh-Hans"))

    def test_polish_keeps_truncation_mark(self):
        src = "Agent Skills that teach coding agents to write and port idiomatic Rust. Works with Claude Code, Codex, a…"
        self.assertIsNotNone(pipe.check_polished(src, "Agent Skills teach coding agents idiomatic Rust, from Claude Code to Codex", "en"))
        self.assertIsNone(pipe.check_polished(src, "Agent Skills teach coding agents to write and port idiomatic Rust: Claude Code, Codex, a…", "en"))

    def test_translation_guard(self):
        src = "Compress PNGs to PNG or WebP: 8–12% smaller than TinyPNG, 7,298 samples."
        self.assertIsNone(pipe.check_translation(src, "把 PNG 压缩成 PNG 或 WebP：比 TinyPNG 小 8–12%，7,298 个样本。"))
        self.assertIsNotNone(pipe.check_translation(src, "把 PNG 压缩成 PNG 或 WebP：比 TinyPNG 小 8–15%，7,298 个样本。"))
        self.assertIsNotNone(pipe.check_translation(src, "把 PNG 压缩成 PNG 或 WebP：比同类小 8–12%，7,298 个样本。"))
        self.assertIsNotNone(pipe.check_translation(src, ""))


class TranslateTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo({"a/one": "Does one thing.", "b/two": "做一件事。", "c/three": "Does three."},
                         cache={"a/one": {"src": "Does one thing.", **{l: f"old {l}" for l in LANG5[1:]}}})
        self.addCleanup(self.repo.close)

    def run_translate(self, runner, **kw):
        return pipe.translate(self.repo.root, self.repo.items, runner, pipe.Budget(60), lambda m: None, **kw)

    def test_only_untranslated_are_sent_and_cache_is_filled(self):
        r = FakeRunner(translate=fake_tr)
        stat = self.run_translate(r)
        self.assertEqual(stat["translated"], 2)
        sent = json.loads(r.calls[0].split("Input items: ", 1)[1].split("\nFor each item", 1)[0])
        self.assertEqual({i["id"] for i in sent}, {"b/two", "c/three"})  # a/one was already translated
        self.assertEqual(set(next(i for i in sent if i["id"] == "b/two")["langs"]), set(LANG5))   # CJK source also gets en
        self.assertEqual(set(next(i for i in sent if i["id"] == "c/three")["langs"]), set(LANG5[1:]))
        cache = self.repo.read("newcomer_i18n.json")
        self.assertEqual(cache["a/one"]["zh-Hans"], "old zh-Hans")  # untouched
        self.assertEqual(cache["c/three"]["src"], "Does three.")
        self.assertEqual(cache["b/two"]["en"], "[en] 做一件事。")

    def test_second_run_makes_no_calls(self):
        self.run_translate(FakeRunner(translate=fake_tr))
        r = FakeRunner(translate=fake_tr)
        self.assertEqual(self.run_translate(r)["todo"], 0)
        self.assertEqual(r.calls, [])

    def test_changed_description_is_translated_again(self):
        self.run_translate(FakeRunner(translate=fake_tr))
        self.repo.items[0]["description"] = "Does one thing, better."
        r = FakeRunner(translate=fake_tr)
        self.run_translate(r)
        self.assertEqual(len(r.calls), 1)
        self.assertEqual(self.repo.read("newcomer_i18n.json")["a/one"]["src"], "Does one thing, better.")

    def test_only_missing_languages_are_requested(self):
        cache = self.repo.read("newcomer_i18n.json")
        del cache["a/one"]["ko"]
        self.repo.write("newcomer_i18n.json", cache)
        r = FakeRunner(translate=fake_tr)
        self.run_translate(r, limit=1)
        sent = json.loads(r.calls[0].split("Input items: ", 1)[1].split("\nFor each item", 1)[0])
        self.assertEqual(sent, [{"id": "a/one", "src": "Does one thing.", "langs": ["ko"]}])

    def test_bad_translation_is_not_written(self):
        repo = Repo({"x/y": "Speeds up 40% on TinyPNG."})
        self.addCleanup(repo.close)
        bad = lambda i: {l: "faster by 50%" for l in i["langs"]}  # noqa: E731
        pipe.translate(repo.root, repo.items, FakeRunner(translate=bad), pipe.Budget(60), lambda m: None)
        self.assertEqual(repo.read("newcomer_i18n.json"), {})

    def test_failure_keeps_everything_and_does_not_raise(self):
        before = self.repo.read("newcomer_i18n.json")
        stat = self.run_translate(FakeRunner(error="boom"))
        self.assertGreaterEqual(stat["errors"], 1)
        self.assertEqual(self.repo.read("newcomer_i18n.json"), before)


class PolishTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo({"a/one": "Does one thing."},
                         cache={"a/one": {"src": "Does one thing.", **{l: f"Does one thing in {l}." for l in LANG5[1:]}}},
                         projects=[project("p/q", "A tool that does 3 things with Ghidra.")])
        self.addCleanup(self.repo.close)

    def run_polish(self, runner, **kw):
        return pipe.polish(self.repo.root, self.repo.items, runner, pipe.Budget(60), kw.pop("targets", pipe.DEFAULT_TARGETS),
                           lambda m: None, **kw)

    def test_polished_text_replaces_source_and_is_remembered(self):
        r = FakeRunner(polish=short)
        stat = self.run_polish(r)
        self.assertEqual(stat["polished"], 5)  # the five project blurbs changed; newcomer texts came back unchanged
        self.assertEqual(self.repo.read("projects.json")[0]["desc"]["en"], "Does 3 things with Ghidra.")
        n = len(r.calls)
        again = FakeRunner(polish=lambda t: self.fail("already polished text must not be sent again"))
        self.assertEqual(self.run_polish(again)["todo"], 0)
        self.assertEqual(again.calls, [])
        self.assertGreater(n, 0)

    def test_rejected_polish_keeps_raw_and_stops_after_max_fails(self):
        evil = FakeRunner(polish=lambda t: t + " 100x faster!!!")
        for _ in range(pipe.MAX_FAILS):
            self.run_polish(evil)
        self.assertEqual(self.repo.read("projects.json")[0]["desc"]["en"], "A tool that does 3 things with Ghidra.")
        calls = len(evil.calls)
        self.run_polish(evil)
        self.assertEqual(len(evil.calls), calls)  # gave up on this exact text

    def test_edited_text_is_polished_again(self):
        self.run_polish(FakeRunner(polish=short))
        projects = self.repo.read("projects.json")
        projects[0]["desc"]["en"] = "A new text with 3 parts for Ghidra."
        self.repo.write("projects.json", projects)
        r = FakeRunner(polish=lambda t: t)
        stat = self.run_polish(r)
        self.assertEqual(stat["todo"], 1)

    def test_suspicious_repos_are_not_polished(self):
        repo = Repo({"warez/Office": "Office 2026 complete setup."}, suspicious=("warez/Office",),
                    cache={"warez/Office": {"src": "Office 2026 complete setup.", **{l: "Office 2026 setup." for l in LANG5[1:]}}})
        self.addCleanup(repo.close)
        r = FakeRunner(polish=lambda t: self.fail("must not be called"))
        stat = pipe.polish(repo.root, repo.items, r, pipe.Budget(60), ("newcomers",), lambda m: None)
        self.assertEqual(stat["todo"], 0)

    def test_categories_only_when_requested(self):
        self.assertNotIn("category", {j["kind"] for j in pipe._polish_jobs(self.repo.root, self.repo.items, pipe.DEFAULT_TARGETS, pipe.load_state(self.repo.root / "data/polish_state.json"))})
        kinds = {j["kind"] for j in pipe._polish_jobs(self.repo.root, self.repo.items, ("categories",), pipe.load_state(self.repo.root / "data/polish_state.json"))}
        self.assertEqual(kinds, {"category"})

    def test_failure_does_not_raise_or_change_files(self):
        before = (self.repo.read("projects.json"), self.repo.read("newcomer_i18n.json"))
        stat = self.run_polish(FakeRunner(error="down"))
        self.assertGreaterEqual(stat["errors"], 1)
        self.assertEqual((self.repo.read("projects.json"), self.repo.read("newcomer_i18n.json")), before)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo({"a/one": "Does one thing."}, projects=[project("p/q", "Does 3 things.")])
        self.addCleanup(self.repo.close)

    def test_without_key_or_model_nothing_changes_and_nothing_is_substituted(self):
        before = self.repo.read("projects.json")
        asked = []
        for why in ("CURSOR_API_KEY is not set", "model 'gemini-3.8-flash-medium' is not available; available: gemini-3-flash"):
            res = pipe.run(self.repo.root, self.repo.new, env={}, log=lambda m: None,
                           make_runner=lambda model: Ready(FakeRunner(translate=lambda i: asked.append(i)), why))
            self.assertTrue(res["translate"]["skipped"] and res["polish"]["skipped"])
        self.assertEqual(asked, [])
        self.assertEqual(self.repo.read("projects.json"), before)
        self.assertEqual(self.repo.read("newcomer_i18n.json"), {})

    def test_model_defaults_to_gemini_3_8_flash_and_env_overrides(self):
        seen = []
        pipe.run(self.repo.root, self.repo.new, env={}, log=lambda m: None, dry_run=False,
                 make_runner=lambda model: seen.append(model) or Ready(FakeRunner(), "off"))
        self.assertEqual(set(seen), {"gemini-3.8-flash-medium"})
        seen.clear()
        pipe.run(self.repo.root, self.repo.new, env={"POLISH_MODEL": "gemini-3.8-flash-high"}, log=lambda m: None,
                 make_runner=lambda model: seen.append(model) or Ready(FakeRunner(), "off"))
        self.assertEqual(set(seen), {"gemini-3.8-flash-high"})

    def test_full_run_translates_then_polishes(self):
        runner = FakeRunner(translate=fake_tr, polish=lambda t: t)
        res = pipe.run(self.repo.root, self.repo.new, env={}, log=lambda m: None, make_runner=lambda m: Ready(runner))
        self.assertEqual(res["translate"]["translated"], 1)
        self.assertGreater(res["polish"]["todo"], 0)
        self.assertEqual(set(self.repo.read("newcomer_i18n.json")["a/one"]) - {"src"}, set(LANG5[1:]))

    def test_run_safe_swallows_everything(self):
        def boom(model):
            raise RuntimeError("kaboom")
        res = pipe.run_safe(self.repo.root, self.repo.new, env={}, log=lambda m: None, make_runner=boom)
        self.assertIn("error", res)

    def test_dry_run_calls_nothing(self):
        res = pipe.run(self.repo.root, self.repo.new, env={}, log=lambda m: None, dry_run=True,
                       make_runner=lambda m: self.fail("must not create a runner"))
        self.assertEqual(res["translate"]["todo"], 1)


class UpdateHookTests(unittest.TestCase):
    def test_i18n_step_never_raises(self):
        with mock.patch.object(up.i18n_pipeline, "run", side_effect=ValueError("x")):
            up.i18n_step({"ok": True})  # must not raise

    def test_update_stars_runs_the_step_before_rendering(self):
        src = (ROOT / "tools/update_stars.py").read_text("utf-8")
        self.assertLess(src.index("i18n_step(new)"), src.index("render_readme.main([])"))
        self.assertIn("--no-i18n", src)


class LlmTests(unittest.TestCase):
    def fake_run(self, out="", code=0, seen=None):
        def run(argv, **kw):
            if seen is not None:
                seen.append((argv, kw))
            return subprocess.CompletedProcess(argv, code, stdout=out, stderr="bad key sk-SECRET" if code else "")
        return run

    def agent(self, listing, **env):
        e = {"CURSOR_API_KEY": "sk-SECRET", "CURSOR_AGENT_BIN": sys.executable, **env}
        return llm.CursorAgent("gemini-3.8-flash-medium", env=e, run=self.fake_run(listing))

    def test_model_must_be_listed_and_is_never_substituted(self):
        ok = self.agent("Available models\n\nauto - Auto\ngemini-3.8-flash-medium - Gemini 3.8 Flash\n")
        self.assertIsNone(ok.unavailable_reason())
        no = self.agent("auto - Auto\ngemini-3-flash - Gemini 3 Flash\ngemini-3.7-flash - Gemini 3.7 Flash\n")
        why = no.unavailable_reason()
        self.assertIn("gemini-3.8-flash-medium", why)
        self.assertIn("gemini-3-flash", why)  # reports what is available

    def test_missing_key_or_cli(self):
        self.assertIn("CURSOR_API_KEY", self.agent("", CURSOR_API_KEY="").unavailable_reason())
        a = llm.CursorAgent(env={"CURSOR_API_KEY": "k", "CURSOR_AGENT_BIN": "definitely-not-installed"})
        self.assertIn("not installed", a.unavailable_reason())

    def test_key_is_only_in_env_never_in_argv_or_errors(self):
        seen = []
        a = llm.CursorAgent("gemini-3.8-flash-medium", env={"CURSOR_API_KEY": "sk-SECRET", "GITHUB_TOKEN": "ghs_x",
                            "CURSOR_AGENT_BIN": sys.executable}, run=self.fake_run("{}", seen=seen))
        a.ask("hi")
        argv, kw = seen[0]
        self.assertNotIn("sk-SECRET", " ".join(argv))
        self.assertEqual(kw["env"]["CURSOR_API_KEY"], "sk-SECRET")
        self.assertNotIn("GITHUB_TOKEN", kw["env"])
        self.assertIn("--mode", argv)
        self.assertEqual(argv[argv.index("ask") - 1], "--mode")
        self.assertEqual(argv[argv.index("--model") + 1], "gemini-3.8-flash-medium")
        b = llm.CursorAgent(env={"CURSOR_API_KEY": "sk-SECRET", "CURSOR_AGENT_BIN": sys.executable}, run=self.fake_run("", code=1))
        with self.assertRaises(llm.LLMError) as cm:
            b.ask("hi")
        self.assertNotIn("sk-SECRET", str(cm.exception))

    def test_extract_json(self):
        self.assertEqual(llm.extract_json('Sure!\n```json\n{"a": "b"}\n```'), {"a": "b"})
        with self.assertRaises(llm.LLMError):
            llm.extract_json("no json here")


class RepoDataTests(unittest.TestCase):
    def test_every_blurb_and_category_has_all_five_languages(self):
        for fname in ("projects.json", "categories.json"):
            for row in json.loads((ROOT / "data" / fname).read_text("utf-8")):
                self.assertEqual(set(row["desc"]), set(LANG5), row.get("name") or row.get("id"))
                for lang, text in row["desc"].items():
                    self.assertTrue(text.strip(), (row.get("name") or row.get("id"), lang))

    def test_guard_accepts_every_real_text_unchanged(self):
        """An unchanged text must always pass, so a model that returns text as is never causes a rejection."""
        for p in json.loads((ROOT / "data/projects.json").read_text("utf-8")):
            for lang, text in p["desc"].items():
                self.assertIsNone(pipe.check_polished(text, text, lang), (p["name"], lang))
        for name, entry in json.loads((ROOT / "data/newcomer_i18n.json").read_text("utf-8")).items():
            for lang in LANG5:
                if lang in entry:
                    self.assertIsNone(pipe.check_polished(entry[lang], entry[lang], lang), (name, lang))
                    self.assertIsNone(pipe.check_translation(entry["src"], entry[lang]), (name, lang))

    def test_secret_is_referenced_not_stored(self):
        wf = (ROOT / ".github/workflows/daily-update.yml").read_text("utf-8")
        self.assertIn("${{ secrets.CURSOR_API_KEY }}", wf)
        self.assertNotRegex(wf, r"CURSOR_API_KEY:\s*(?!\$\{\{)\S")
        for f in list((ROOT / "tools").glob("*.py")) + list((ROOT / "data").glob("*.json")):
            self.assertNotRegex(f.read_text("utf-8"), r"key_[A-Za-z0-9]{16,}", f.name)


if __name__ == "__main__":
    unittest.main()
