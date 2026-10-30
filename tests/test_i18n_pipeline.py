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
import newcomer_i18n as nci  # noqa: E402
import update_stars as up  # noqa: E402

LANG5 = ("en", "zh-Hans", "zh-Hant", "ja", "ko")


class FakeRunner:
    """Answers translate/polish prompts from a callback; counts calls."""

    def __init__(self, translate=None, polish=None, error=None, hook=None):
        self.calls, self.translate, self.polish, self.error = [], translate, polish, error
        self.hook = hook or (lambda item: {l: f"hook {l}" for l in item["langs"]})

    def ask(self, prompt):
        self.calls.append(prompt)
        if self.error:
            raise llm.LLMError(self.error)
        if prompt.startswith("You translate"):
            items = json.loads(prompt.split("Input items: ", 1)[1].split("\nFor each item", 1)[0])
            return json.dumps({i["id"]: self.translate(i) for i in items}, ensure_ascii=False)
        if prompt.startswith("You write the ONE-LINE hook"):
            items = json.loads(prompt.split("Input items: ", 1)[1].split("\nFor each item", 1)[0])
            return json.dumps({i["id"]: self.hook(i) for i in items}, ensure_ascii=False)
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
        self.write("translation_library.json", nci.from_legacy(cache or {}))
        self.write("projects.json", projects or [])
        self.write("categories.json", [{"id": "ai", "desc": {l: f"cat {l}" for l in LANG5}}])

    def write(self, name, data):
        (self.root / "data" / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")

    def read(self, name):
        return json.loads((self.root / "data" / name).read_text("utf-8"))

    def entry(self, name, src):
        return (self.read("translation_library.json")["entries"].get(name) or {}).get(nci.src_hash(src))

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
        self.assertEqual(self.repo.entry("a/one", "Does one thing.")["zh-Hans"], "old zh-Hans")  # untouched
        self.assertEqual(self.repo.entry("c/three", "Does three.")["src"], "Does three.")
        self.assertEqual(self.repo.entry("b/two", "做一件事。")["en"], "[en] 做一件事。")

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
        self.assertEqual(self.repo.entry("a/one", "Does one thing, better.")["ja"], "[ja] Does one thing, better.")
        self.assertEqual(self.repo.entry("a/one", "Does one thing.")["ja"], "old ja")  # the old text stays in the library

    def test_only_missing_languages_are_requested(self):
        lib = self.repo.read("translation_library.json")
        del lib["entries"]["a/one"][nci.src_hash("Does one thing.")]["ko"]
        self.repo.write("translation_library.json", lib)
        r = FakeRunner(translate=fake_tr)
        self.run_translate(r, limit=1)
        sent = json.loads(r.calls[0].split("Input items: ", 1)[1].split("\nFor each item", 1)[0])
        self.assertEqual(sent, [{"id": "a/one", "src": "Does one thing.", "langs": ["ko"]}])

    def test_bad_translation_is_not_written(self):
        repo = Repo({"x/y": "Speeds up 40% on TinyPNG."})
        self.addCleanup(repo.close)
        bad = lambda i: {l: "faster by 50%" for l in i["langs"]}  # noqa: E731
        pipe.translate(repo.root, repo.items, FakeRunner(translate=bad), pipe.Budget(60), lambda m: None)
        self.assertEqual(repo.read("translation_library.json")["entries"], {})

    def test_failure_keeps_everything_and_does_not_raise(self):
        def texts():  # `seen` is bookkeeping, the translations are what must not change
            return {n: {h: {k: v for k, v in e.items() if k != "seen"} for h, e in vs.items()}
                    for n, vs in self.repo.read("translation_library.json")["entries"].items()}
        before = texts()
        stat = self.run_translate(FakeRunner(error="boom"))
        self.assertGreaterEqual(stat["errors"], 1)
        self.assertEqual(texts(), before)


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
        before = (self.repo.read("projects.json"), self.repo.read("translation_library.json"))
        stat = self.run_polish(FakeRunner(error="down"))
        self.assertGreaterEqual(stat["errors"], 1)
        self.assertEqual((self.repo.read("projects.json"), self.repo.read("translation_library.json")), before)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo({"a/one": "Does one thing."}, projects=[project("p/q", "Does 3 things.")])
        self.addCleanup(self.repo.close)

    def test_without_key_or_model_nothing_changes_and_nothing_is_substituted(self):
        before = self.repo.read("projects.json")
        asked = []
        for why in ("CURSOR_API_KEY is not set", "model 'gemini-3.8-flash-medium' is not available; available: gemini-3-flash"):
            res = pipe.run(self.repo.root, self.repo.new, env={}, log=lambda m: None,
                           make_runner=lambda backend, model: Ready(FakeRunner(translate=lambda i: asked.append(i)), why))
            self.assertTrue(res["translate"]["skipped"] and res["polish"]["skipped"])
        self.assertEqual(asked, [])
        self.assertEqual(self.repo.read("projects.json"), before)
        self.assertEqual(self.repo.read("translation_library.json")["entries"], {})

    def test_backends_and_models_default_to_cursor_translate_agy_polish(self):
        seen = []
        pipe.run(self.repo.root, self.repo.new, env={}, log=lambda m: None,
                 make_runner=lambda backend, model: seen.append((backend, model)) or Ready(FakeRunner(), "off"))
        self.assertEqual(set(seen), {("cursor", "gemini-3.8-flash-medium"), ("agy", "gemini-3.8-flash-medium")})
        seen.clear()
        env = {"POLISH_MODEL": "gemini-3.8-flash-high", "I18N_TRANSLATE_BACKEND": "agy"}
        pipe.run(self.repo.root, self.repo.new, env=env, log=lambda m: None,
                 make_runner=lambda backend, model: seen.append((backend, model)) or Ready(FakeRunner(), "off"))
        self.assertEqual(set(seen), {("agy", "gemini-3.8-flash-high")})

    def test_translate_only_never_touches_the_polish_backend(self):
        seen = []
        pipe.run(self.repo.root, self.repo.new, do_polish=False, env={}, log=lambda m: None,
                 make_runner=lambda backend, model: seen.append(backend) or Ready(FakeRunner(translate=fake_tr), None))
        self.assertEqual(set(seen), {"cursor"})  # what CI does

    def test_full_run_translates_then_polishes(self):
        runner = FakeRunner(translate=fake_tr, polish=lambda t: t)
        res = pipe.run(self.repo.root, self.repo.new, env={}, log=lambda m: None, make_runner=lambda b, m: Ready(runner))
        self.assertEqual(res["translate"]["translated"], 1)
        self.assertGreater(res["polish"]["todo"], 0)
        self.assertEqual(set(self.repo.entry("a/one", "Does one thing.")) - {"src", "seen", "hook"}, set(LANG5[1:]))
        self.assertEqual(set(self.repo.entry("a/one", "Does one thing.")["hook"]), set(LANG5))

    def test_run_safe_swallows_everything(self):
        def boom(model):
            raise RuntimeError("kaboom")
        res = pipe.run_safe(self.repo.root, self.repo.new, env={}, log=lambda m: None, make_runner=lambda b, m: boom(m))
        self.assertIn("error", res)

    def test_dry_run_calls_nothing(self):
        res = pipe.run(self.repo.root, self.repo.new, env={}, log=lambda m: None, dry_run=True,
                       make_runner=lambda b, m: self.fail("must not create a runner"))
        self.assertEqual(res["translate"]["todo"], 1)


class UpdateHookTests(unittest.TestCase):
    def test_i18n_step_never_raises(self):
        with mock.patch.object(up.i18n_pipeline, "run", side_effect=ValueError("x")):
            up.i18n_step({"ok": True})  # must not raise

    def test_polish_only_when_asked_so_ci_translates_only(self):
        calls = []
        with mock.patch.object(up.i18n_pipeline, "run_safe", lambda root, new, **kw: calls.append(kw)):
            with mock.patch.dict("os.environ", {}, clear=False):
                os_env = up.os.environ
                os_env.pop("I18N_POLISH", None)
                up.i18n_step({})
                os_env["I18N_POLISH"] = "1"
                try:
                    up.i18n_step({})
                finally:
                    os_env.pop("I18N_POLISH", None)
        self.assertEqual([c["do_polish"] for c in calls], [False, True])

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


AGY_MODELS = """Fetching available models...
gemini-4-argon-high       Gemini 4 Argon (High)
gemini-3.8-flash-high     Gemini 3.8 Flash (High)
gemini-3.8-flash-medium   Gemini 3.8 Flash (Medium)
gemini-3.7-flash-medium   Gemini 3.7 Flash (Medium)
"""


class AgyTests(unittest.TestCase):
    def agent(self, outputs, seen=None, model="gemini-3.8-flash-medium", env=None):
        def run(argv, **kw):
            if seen is not None:
                seen.append((argv, kw))
            out = outputs(argv) if callable(outputs) else outputs
            return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")
        e = {"AGY_BIN": sys.executable, "CURSOR_API_KEY": "cursor-secret", "GITHUB_TOKEN": "ghs_x", **(env or {})}
        return llm.AgyAgent(model, env=e, run=run)

    def test_exact_slug_must_be_listed_and_nothing_is_substituted(self):
        self.assertIsNone(self.agent(AGY_MODELS).unavailable_reason())
        why = self.agent(AGY_MODELS, model="gemini-3.8-flash-low").unavailable_reason()
        self.assertIn("gemini-3.8-flash-low", why)
        self.assertIn("gemini-3.8-flash-medium", why)  # lists what is available
        self.assertIn("gemini-4-argon-high", why)

    def test_signed_out_is_reported_not_raised(self):
        why = self.agent("Fetching available models...\nError: Please sign in to view available models.\n").unavailable_reason()
        self.assertIn("sign in", why)

    def test_missing_binary(self):
        a = llm.AgyAgent(env={"AGY_BIN": "definitely-not-installed"})
        self.assertIn("not installed", a.unavailable_reason())

    def test_ask_pins_model_runs_in_temp_dir_and_hides_other_credentials(self):
        seen = []
        a = self.agent('{"status":"SUCCESS","response":"{\\"0\\": \\"hi\\"}\\n"}', seen=seen)
        self.assertEqual(a.ask("polish this"), '{"0": "hi"}\n')
        argv, kw = seen[0]
        self.assertEqual(argv[argv.index("--model") + 1], "gemini-3.8-flash-medium")
        self.assertEqual(argv[argv.index("--output-format") + 1], "json")
        self.assertIn("-p", argv)
        self.assertNotIn(kw["cwd"], (str(ROOT), "."))
        self.assertNotIn("GITHUB_TOKEN", kw["env"])
        self.assertNotIn("CURSOR_API_KEY", kw["env"])

    def test_error_status_raises_llm_error(self):
        a = self.agent('{"status":"ERROR","response":"","error":"model x is not recognized"}')
        with self.assertRaises(llm.LLMError):
            a.ask("hi")

    def test_factory(self):
        self.assertIsInstance(llm.make_agent("agy", "m", env={}), llm.AgyAgent)
        self.assertNotIsInstance(llm.make_agent("cursor", "m", env={}), llm.AgyAgent)
        with self.assertRaises(ValueError):
            llm.make_agent("other", "m")

    def test_local_scripts_exist_and_never_embed_credentials(self):
        for name in ("polish_local.sh", "local_daily.sh"):
            text = (ROOT / "tools" / name).read_text("utf-8")
            self.assertNotRegex(text, r"GEMINI_API_KEY\s*=\s*\S", name)
        text = (ROOT / "tools/polish_local.sh").read_text("utf-8")
        self.assertIn("agy models", text)
        self.assertIn("gemini-3.8-flash-medium", text)
        wf = (ROOT / ".github/workflows/daily-update.yml").read_text("utf-8")
        self.assertNotIn("agy", wf.replace("Polish is NOT done here: it runs on the owner's machine with `agy` (tools/polish_local.sh).", ""))
        self.assertNotIn("POLISH_MODEL", wf)


class LibraryReuseTests(unittest.TestCase):
    """Token saving: a library hit never reaches the model; only a changed source costs a call."""

    def setUp(self):
        self.repo = Repo({"a/one": "Does one thing.", "b/two": "Does two things."})
        self.addCleanup(self.repo.close)
        self.logs = []

    def translate(self, runner, **kw):
        return pipe.translate(self.repo.root, self.repo.items, runner, pipe.Budget(60), self.logs.append, **kw)

    def test_zero_model_calls_when_everything_is_in_the_library(self):
        first = FakeRunner(translate=fake_tr)
        self.translate(first)
        self.assertEqual(len(first.calls), 1)
        for _ in range(3):  # any number of later runs
            r = FakeRunner(translate=lambda i: self.fail("a library hit must not reach the model"))
            stat = self.translate(r)
            self.assertEqual(r.calls, [])
            self.assertEqual((stat["hits"], stat["total"], stat["calls"]), (2, 2, 0))

    def test_run_with_everything_cached_does_not_even_build_a_translate_runner(self):
        self.translate(FakeRunner(translate=fake_tr))
        built = []
        res = pipe.run(self.repo.root, self.repo.new, do_polish=False, do_hooks=False, env={}, log=self.logs.append,
                       make_runner=lambda b, m: built.append(b) or self.fail("no runner needed on a full hit"))
        self.assertEqual(built, [])
        self.assertEqual(res["translate"]["calls"], 0)
        self.assertTrue(any("2/2 hits (100%)" in m and "0 model calls" in m for m in self.logs), self.logs)

    def test_only_the_changed_source_is_sent_and_the_rest_are_hits(self):
        self.translate(FakeRunner(translate=fake_tr))
        self.repo.items[1]["description"] = "Does two things, faster."
        r = FakeRunner(translate=fake_tr)
        stat = self.translate(r)
        sent = json.loads(r.calls[0].split("Input items: ", 1)[1].split("\nFor each item", 1)[0])
        self.assertEqual([i["id"] for i in sent], ["b/two"])
        self.assertEqual((stat["hits"], stat["new"], stat["calls"]), (1, 1, 1))

    def test_same_text_in_another_repo_is_not_a_hit(self):
        self.translate(FakeRunner(translate=fake_tr))
        self.repo.items.append({"name": "c/copy", "description": "Does one thing."})
        r = FakeRunner(translate=fake_tr)
        self.translate(r)
        sent = json.loads(r.calls[0].split("Input items: ", 1)[1].split("\nFor each item", 1)[0])
        self.assertEqual([i["id"] for i in sent], ["c/copy"])

    def test_log_prints_hit_and_new_counts(self):
        self.translate(FakeRunner(translate=fake_tr))
        self.logs.clear()
        self.repo.items.append({"name": "c/new", "description": "Brand new."})
        self.translate(FakeRunner(translate=fake_tr))
        line = next(m for m in self.logs if m.startswith("translate: library"))
        self.assertIn("2/3 hits (67%)", line)
        self.assertIn("1 new", line)
        self.assertIn("1 to send to the model", line)

    def test_dry_run_reports_without_writing(self):
        before = self.repo.read("translation_library.json")
        stat = self.translate(FakeRunner(translate=fake_tr), dry_run=True)
        self.assertEqual((stat["todo"], stat["calls"]), (2, 0))
        self.assertEqual(self.repo.read("translation_library.json"), before)

    def test_only_unpolished_entries_are_polished(self):
        self.translate(FakeRunner(translate=fake_tr))
        first = FakeRunner(polish=lambda t: t)
        pipe.polish(self.repo.root, self.repo.items, first, pipe.Budget(60), ("newcomers",), self.logs.append)
        self.assertGreater(len(first.calls), 0)
        self.repo.items.append({"name": "c/new", "description": "Brand new."})
        self.translate(FakeRunner(translate=fake_tr))
        r = FakeRunner(polish=lambda t: t)
        stat = pipe.polish(self.repo.root, self.repo.items, r, pipe.Budget(60), ("newcomers",), self.logs.append)
        self.assertEqual(stat["todo"], 4)  # c/new in four languages; the eight polished texts are skipped
        self.assertEqual((stat["skipped"], stat["candidates"]), (8, 12))
        self.assertTrue(any("8/12 texts already polished" in m for m in self.logs))

    def test_changed_source_means_a_new_unpolished_entry(self):
        self.translate(FakeRunner(translate=fake_tr))
        pipe.polish(self.repo.root, self.repo.items, FakeRunner(polish=lambda t: t), pipe.Budget(60), ("newcomers",), lambda m: None)
        self.repo.items[0]["description"] = "Does one thing, faster."
        self.translate(FakeRunner(translate=fake_tr))
        stat = pipe.polish(self.repo.root, self.repo.items, FakeRunner(polish=lambda t: t), pipe.Budget(60), ("newcomers",), lambda m: None)
        self.assertEqual(stat["todo"], 4)

    def test_translate_hits_refresh_seen_at_most_weekly(self):
        self.translate(FakeRunner(translate=fake_tr), today="2026-10-01")
        self.translate(FakeRunner(translate=fake_tr), today="2026-10-03")
        self.assertEqual(self.repo.entry("a/one", "Does one thing.")["seen"], "2026-10-01")
        self.translate(FakeRunner(translate=fake_tr), today="2026-10-20")
        self.assertEqual(self.repo.entry("a/one", "Does one thing.")["seen"], "2026-10-20")


class LibraryLogWhenSkippedTests(unittest.TestCase):
    def test_hit_and_new_counts_are_logged_even_without_a_model(self):
        repo = Repo({"a/one": "Does one thing.", "b/two": "Does two."},
                    cache={"a/one": {"src": "Does one thing.", **{l: "t" for l in LANG5[1:]}}})
        self.addCleanup(repo.close)
        logs = []
        res = pipe.run(repo.root, repo.new, do_polish=False, env={}, log=logs.append,
                       make_runner=lambda b, m: Ready(FakeRunner(), "no key"))
        self.assertTrue(res["translate"]["skipped"])
        self.assertTrue(any("1/2 hits (50%)" in m and "1 new" in m for m in logs), logs)


class GlossaryTests(unittest.TestCase):
    GLOS = json.loads((ROOT / "data/glossary.json").read_text("utf-8"))

    def test_only_terms_present_in_the_texts_are_sent(self):
        g = pipe.glossary_for(["An agent that reads your repo"], ["zh-Hans", "ja"], self.GLOS)
        self.assertIn("agent = 智能体 (zh-Hans) / エージェント (ja)", g)
        self.assertIn("repo = 仓库 (zh-Hans)", g)
        self.assertNotIn("dataset", g)
        self.assertNotIn("星标", g)

    def test_no_terms_means_a_short_prompt(self):
        g = pipe.glossary_for(["Fast."], ["ko"], self.GLOS)
        self.assertEqual(g, pipe.BASE_RULES)

    def test_prompt_contains_glossary_terms_and_stays_smaller_than_the_full_list(self):
        repo = Repo({"a/one": "An agent skill."})
        self.addCleanup(repo.close)
        shutil.copy(ROOT / "data/glossary.json", repo.root / "data/glossary.json")
        r = FakeRunner(translate=fake_tr)
        pipe.translate(repo.root, repo.items, r, pipe.Budget(60), lambda m: None)
        self.assertIn("智能体", r.calls[0])
        self.assertIn("技能", r.calls[0])
        self.assertNotIn("数据集", r.calls[0])

    def test_glossary_covers_every_language_and_uses_the_house_wording(self):
        for t in self.GLOS["terms"]:
            self.assertEqual({"en", "zh-Hans", "zh-Hant", "ja", "ko"}, set(t), t)
        star = next(t for t in self.GLOS["terms"] if t["en"] == "star")
        self.assertEqual((star["zh-Hans"], star["zh-Hant"]), ("星标", "星號"))
        agent = next(t for t in self.GLOS["terms"] if t["en"] == "agent")
        self.assertEqual((agent["zh-Hans"], agent["zh-Hant"], agent["ja"], agent["ko"]), ("智能体", "代理", "エージェント", "에이전트"))


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
        lib = json.loads((ROOT / "data/translation_library.json").read_text("utf-8"))
        for name, versions in lib["entries"].items():
            for entry in versions.values():
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
