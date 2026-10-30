"""One-line hooks for the ranking tables: length rule per language, old entries untouched, rules in the prompts."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import hooks  # noqa: E402
import i18n_pipeline as pipe  # noqa: E402
import newcomer_i18n as nci  # noqa: E402
import render_readme  # noqa: E402
from test_i18n_pipeline import FakeRunner, LANG5, Repo, project  # noqa: E402

BASELINE = json.loads((ROOT / "tests/fixtures/pre_hook_baseline.json").read_text("utf-8"))
PROJECTS = json.loads((ROOT / "data/projects.json").read_text("utf-8"))
LIB = nci.load(ROOT / "data/translation_library.json")


def all_hooks():
    for p in PROJECTS:
        yield p["name"], p.get("hook") or {}, " ".join(p["desc"].values())
    for name, versions in LIB["entries"].items():
        for entry in versions.values():
            yield name, entry.get("hook") or {}, " ".join([entry["src"]] + [entry.get(l, "") for l in LANG5])


class LengthRuleTests(unittest.TestCase):
    def test_limits_are_the_agreed_ones(self):
        self.assertEqual(hooks.MAX_WIDTH["en"], 60)
        self.assertLessEqual(hooks.MAX_WIDTH["zh-Hans"], 36)  # 18 Chinese characters
        self.assertEqual(hooks.MAX_WIDTH["zh-Hant"], hooks.MAX_WIDTH["zh-Hans"])
        self.assertLessEqual(hooks.MAX_WIDTH["ja"], 56)       # 28 characters
        self.assertLessEqual(hooks.MAX_WIDTH["ko"], 60)       # 30 characters

    def test_every_stored_hook_obeys_the_length_rule_in_every_language(self):
        seen = 0
        for name, hook, detail in all_hooks():
            for lang, text in hook.items():
                self.assertIn(lang, LANG5, name)
                self.assertIsNone(hooks.check_hook(text, lang, detail), (name, lang, text))
                seen += 1
        self.assertGreater(seen, 500)

    def test_each_language_has_its_own_length_test(self):
        long_en = "x" * 61
        too_long = {"en": long_en, "zh-Hans": "一" * 19, "zh-Hant": "一" * 19, "ja": "あ" * 29, "ko": "가" * 31}
        fine = {"en": "x" * 60, "zh-Hans": "一" * 18, "zh-Hant": "一" * 18, "ja": "あ" * 28, "ko": "가" * 30}
        for lang in LANG5:
            self.assertIn("too long", hooks.check_hook(too_long[lang], lang) or "", lang)
            self.assertIsNone(hooks.check_hook(fine[lang], lang), lang)

    def test_the_old_morluto_rea_text_is_not_a_hook_but_the_new_one_is(self):
        rea = next(p for p in PROJECTS if p["name"] == "morluto/rea")
        for lang in LANG5:
            self.assertIsNotNone(hooks.check_hook(rea["desc"][lang], lang), lang)  # the long text fails the rule
            self.assertIsNone(hooks.check_hook(rea["hook"][lang], lang, rea["desc"][lang]), lang)
        self.assertEqual(rea["hook"]["zh-Hans"], "让 AI 帮你逆向、复刻任何软件")
        self.assertLessEqual(len(rea["hook"]["zh-Hans"].replace(" ", "")), 15)

    def test_rejects_hype_exclamation_ellipsis_new_numbers_and_multiline(self):
        d = "A tool with 3 parts."
        self.assertIsNotNone(hooks.check_hook("Wow!", "en", d))
        self.assertIsNotNone(hooks.check_hook("It does more…", "en", d))
        self.assertIsNotNone(hooks.check_hook("A game-changer", "en", d))
        self.assertIsNotNone(hooks.check_hook("炸裂的工具", "zh-Hans", d))
        self.assertIsNotNone(hooks.check_hook("10x faster", "en", d))
        self.assertIsNone(hooks.check_hook("Three parts", "en", d))
        self.assertIsNone(hooks.check_hook("3 parts in one", "en", d))
        self.assertIsNotNone(hooks.check_hook("a\nb", "en", d))
        self.assertIsNotNone(hooks.check_hook("", "en", d))

    def test_every_project_has_a_hook_in_all_five_languages(self):
        for p in PROJECTS:
            self.assertEqual(set(p.get("hook") or {}), set(LANG5), p["name"])

    def test_every_ranked_new_repo_has_a_hook_or_is_listed_as_pending(self):
        """Informational like the translation gaps: a repo that arrived after the last hook run shows its translation."""
        stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))
        items = pipe.displayed_newcomers(stats.get("newcomers"))
        missing = [it["name"] for it in items if it.get("description")
                   and not all(nci.get_hook(LIB, it["name"], it["description"], l) for l in LANG5)]
        self.assertEqual(missing, [], "run: python3 tools/i18n_pipeline.py --hooks")


class OldEntriesSurviveTests(unittest.TestCase):
    """The long descriptions and every translation stay exactly as they were; the hook is a separate field."""

    def test_every_old_project_description_is_unchanged(self):
        now = {p["name"]: p["desc"] for p in PROJECTS}
        self.assertEqual(set(BASELINE["projects"]) - set(now), set())
        for name, desc in BASELINE["projects"].items():
            self.assertEqual(now[name], desc, name)

    def test_every_old_library_entry_is_still_there_unchanged(self):
        self.assertGreaterEqual(len(BASELINE["library"]), 59)
        for name, versions in BASELINE["library"].items():
            for h, old in versions.items():
                new = LIB["entries"][name][h]
                for key, value in old.items():
                    if key != "seen":  # `seen` is only the last-used day
                        self.assertEqual(new[key], value, (name, h, key))
                self.assertEqual(h, nci.src_hash(old["src"]))

    def test_old_entries_still_match_for_reuse(self):
        for name, versions in BASELINE["library"].items():
            for old in versions.values():
                self.assertEqual(nci.missing_langs(LIB, name, old["src"]), [], name)
                for lang in LANG5:
                    if old.get(lang):
                        self.assertEqual(nci.get(LIB, name, old["src"], lang), old[lang])

    def test_details_pages_carry_every_old_text_unchanged(self):
        for lang in LANG5:
            page = (ROOT / "docs" / render_readme.details_name(lang)).read_text("utf-8")
            for name, desc in BASELINE["projects"].items():
                self.assertIn(render_readme._cell(desc[lang]), page, (lang, name))
        stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))
        for lang in LANG5:
            page = (ROOT / "docs" / render_readme.details_name(lang)).read_text("utf-8")
            for it in pipe.displayed_newcomers(stats.get("newcomers")):
                if it.get("description"):
                    self.assertIn(render_readme._cell(nci.pick(LIB, it["name"], it["description"], lang)), page, (lang, it["name"]))

    def test_tables_show_the_hook_and_not_the_long_text(self):
        rea = next(p for p in PROJECTS if p["name"] == "morluto/rea")
        for lang in LANG5:
            readme = (ROOT / render_readme.LANGS[lang][0]).read_text("utf-8")
            self.assertIn(rea["hook"][lang], readme, lang)
            self.assertNotIn(rea["desc"][lang], readme, lang)
            self.assertIn("Ghidra", (ROOT / "docs" / render_readme.details_name(lang)).read_text("utf-8"))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo({"a/one": "Does one thing with Ghidra.", "b/crack": "Pro 2026 full installer, pre-activated."},
                         suspicious=("b/crack",))
        self.addCleanup(self.repo.close)
        self.repo.write("projects.json", [project("p/proj", "A long English description of 3 things.")])
        self.budget = pipe.Budget(60)

    def run_hooks(self, runner, **kw):
        return pipe.write_hooks(self.repo.root, self.repo.items, runner, self.budget, lambda m: None, **kw)

    def test_prompt_carries_the_rule_with_every_limit_and_the_example(self):
        r = FakeRunner()
        self.run_hooks(r)
        prompt = r.calls[0]
        for needle in ("English <= 60", "18 Chinese characters", "Japanese <= 28", "Korean <= 30",
                       "让 AI 帮你逆向、复刻任何软件", "never invent", "literal"):
            self.assertIn(needle.lower(), prompt.lower(), needle)
        self.assertIn('"literal": true', prompt)  # the suspicious repo is flagged to the model

    def test_polish_prompt_keeps_the_details_and_points_at_the_hooks(self):
        self.assertIn("one-line hook", pipe.POLISH_PROMPT)
        self.assertIn("keep the details", pipe.POLISH_PROMPT)

    def test_hooks_are_added_next_to_the_translations_and_never_change_them(self):
        before = {"o/r": {"src": "Original text", "zh-Hans": "原文", "zh-Hant": "原文", "ja": "原文", "ko": "원문"}}
        repo = Repo({"o/r": "Original text"}, cache=before)
        self.addCleanup(repo.close)
        old_entry = dict(repo.entry("o/r", "Original text"))
        r = FakeRunner()
        stat = pipe.write_hooks(repo.root, repo.items, r, self.budget, lambda m: None)
        new_entry = repo.entry("o/r", "Original text")
        self.assertEqual({k: v for k, v in new_entry.items() if k not in ("hook", "seen")},
                         {k: v for k, v in old_entry.items() if k != "seen"})
        self.assertEqual(set(new_entry["hook"]), set(LANG5))
        self.assertEqual(stat["written"], 5)
        self.assertEqual(nci.get(nci.load(repo.root / "data/translation_library.json"), "o/r", "Original text", "ja"), "原文")

    def test_second_run_costs_no_model_call(self):
        self.run_hooks(FakeRunner())
        r = FakeRunner(hook=lambda i: self.fail("a stored hook must not be asked for again"))
        stat = self.run_hooks(r)
        self.assertEqual((stat["todo"], r.calls), (0, []))

    def test_too_long_or_hyped_replies_are_rejected_and_the_old_text_stays(self):
        bad = lambda i: {l: "x" * 200 if l == "en" else "炸裂" for l in i["langs"]}
        stat = self.run_hooks(FakeRunner(hook=bad))
        self.assertEqual(stat["written"], 0)
        self.assertGreater(stat["rejected"], 0)
        self.assertIsNone((self.repo.entry("a/one", "Does one thing with Ghidra.") or {}).get("hook"))
        proj = self.repo.read("projects.json")[0]
        self.assertNotIn("hook", proj)
        self.assertEqual(proj["desc"], project("p/proj", "A long English description of 3 things.")["desc"])

    def test_a_stored_hook_that_breaks_the_rule_is_written_again_only_for_that_language(self):
        self.run_hooks(FakeRunner())
        rows = self.repo.read("projects.json")
        rows[0]["hook"]["zh-Hans"] = "一" * 40
        self.repo.write("projects.json", rows)
        seen = []
        r = FakeRunner(hook=lambda i: seen.append(i["langs"]) or {l: f"new {l}" for l in i["langs"]})
        self.run_hooks(r)
        self.assertEqual(seen, [["zh-Hans"]])
        self.assertEqual(self.repo.read("projects.json")[0]["hook"]["zh-Hans"], "new zh-Hans")

    def test_polish_never_touches_hooks(self):
        self.run_hooks(FakeRunner())
        before = self.repo.read("projects.json")[0]["hook"]
        pipe.polish(self.repo.root, self.repo.items, FakeRunner(polish=lambda t: t), self.budget,
                    targets=("projects",), log=lambda m: None)
        self.assertEqual(self.repo.read("projects.json")[0]["hook"], before)

    def test_run_has_a_hook_stage_that_uses_the_translate_backend_unless_told_otherwise(self):
        seen = []
        pipe.run(self.repo.root, self.repo.new, do_translate=False, do_polish=False, env={}, log=lambda m: None,
                 make_runner=lambda b, m: seen.append(b) or type("R", (), {"unavailable_reason": lambda s: "off"})())
        self.assertEqual(seen, ["cursor"])
        seen.clear()
        pipe.run(self.repo.root, self.repo.new, do_translate=False, do_polish=False, env={"I18N_HOOK_BACKEND": "agy"},
                 log=lambda m: None,
                 make_runner=lambda b, m: seen.append(b) or type("R", (), {"unavailable_reason": lambda s: "off"})())
        self.assertEqual(seen, ["agy"])

    def test_local_polish_script_writes_hooks_through_agy(self):
        sh = (ROOT / "tools/polish_local.sh").read_text("utf-8")
        self.assertIn("--hooks --polish", sh)
        self.assertIn("I18N_HOOK_BACKEND=agy", sh)
        self.assertIn("docs/DETAILS*.md", sh)


if __name__ == "__main__":
    unittest.main()
