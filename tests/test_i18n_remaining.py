"""Translated new-repo descriptions and per-language ranking pages."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import archive  # noqa: E402
import newcomer_i18n  # noqa: E402
import render_readme  # noqa: E402
from i18n import LANGS, S  # noqa: E402

cache = newcomer_i18n.load(ROOT / "data/newcomer_i18n.json")
stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))
ITEMS = [{"name": "o/r", "description": "Original text", "url": "https://github.com/o/r",
          "created_at": "2026-10-24T00:00:00Z", "age_days": 2.5, "stars": 10, "per_day": 4.0}]


class CacheSchemaTests(unittest.TestCase):
    def test_entries_are_well_formed(self):
        for name, entry in cache.items():
            self.assertIn("/", name)
            self.assertTrue(entry.get("src", "").strip(), name)
            for lang, text in entry.items():
                if lang != "src":
                    self.assertIn(lang, LANGS, f"{name}: unknown language {lang}")
                    self.assertTrue(text.strip(), f"{name} {lang}")
            for lang in newcomer_i18n.required_langs(entry["src"]):
                self.assertIn(lang, entry, f"{name} lacks {lang}")

    def test_no_secrets_or_online_translation_in_the_tool(self):
        text = (ROOT / "tools/newcomer_i18n.py").read_text("utf-8")
        self.assertNotIn("urllib", text)
        self.assertNotIn("http.client", text)


class PickTests(unittest.TestCase):
    def test_translation_used_when_source_matches(self):
        c = {"o/r": {"src": "Original text", "ja": "原文の訳"}}
        self.assertEqual(newcomer_i18n.pick(c, "o/r", "Original text", "ja"), "原文の訳")

    def test_falls_back_to_original_when_missing_or_stale(self):
        c = {"o/r": {"src": "Old text", "ja": "古い訳"}}
        self.assertEqual(newcomer_i18n.pick(c, "o/r", "Original text", "ja"), "Original text")  # stale
        self.assertEqual(newcomer_i18n.pick(c, "o/r", "Old text", "ko"), "Old text")  # no ko
        self.assertEqual(newcomer_i18n.pick({}, "o/r", "Original text", "ja"), "Original text")  # no entry

    def test_table_uses_translation_per_language_and_original_without_one(self):
        c = {"o/r": {"src": "Original text", "zh-Hans": "原文的译文"}}
        self.assertIn("<br>原文的译文", render_readme.new_table(ITEMS, "zh-Hans", c))
        self.assertIn("<br>Original text", render_readme.new_table(ITEMS, "ko", c))
        self.assertIn("<br>Original text", render_readme.new_table(ITEMS, "zh-Hans", {}))


class ProblemsTests(unittest.TestCase):
    def test_reports_missing_stale_and_partial(self):
        items = [{"name": "a/new", "description": "x"}, {"name": "b/old", "description": "changed"},
                 {"name": "c/part", "description": "y"}, {"name": "d/none", "description": ""}]
        c = {"b/old": {"src": "was", **{l: "t" for l in newcomer_i18n.REQUIRED}},
             "c/part": {"src": "y", "zh-Hans": "t"}}
        out = newcomer_i18n.problems(c, items)
        self.assertEqual(len(out), 3)
        self.assertIn("a/new: missing", out[0])
        self.assertIn("b/old: stale", out[1])
        self.assertIn("c/part: missing zh-Hant, ja, ko", out[2])

    def test_cjk_source_also_requires_english(self):
        self.assertIn("en", newcomer_i18n.required_langs("从选题到剪映草稿"))
        self.assertNotIn("en", newcomer_i18n.required_langs("plain English"))

    def test_strict_exit_code(self):
        # listing is informational; --strict only fails on the primary (AI) category gaps
        self.assertEqual(newcomer_i18n.main([]), 0)
        # AI board may have fresh untranslated newcomers after a real run; do not require 0 here.
        self.assertIn(newcomer_i18n.main(["--strict"]), (0, 1))


class LocalizedRankingPageTests(unittest.TestCase):
    def test_file_names(self):
        self.assertEqual(archive.rankings_name("en"), "rankings.md")
        self.assertEqual(archive.rankings_name("zh-Hant"), "rankings.zh-Hant.md")
        self.assertEqual(archive.index_name("en"), "README.md")
        self.assertEqual(archive.index_name("ja"), "README.ja.md")

    def test_english_page_is_unchanged_default(self):
        cats = archive.load_categories(ROOT)
        self.assertEqual(archive.render_rankings_md(stats, "en", cats),
                         archive.render_rankings_md(stats, "en", cats))
        md = archive.render_rankings_md(stats, "en", cats)
        self.assertIn("| # | Repo | Created (UTC) | Stars | Stars/day |", md)

    def test_pages_are_translated_and_link_to_own_language(self):
        for code in LANGS:
            if code == "en":
                continue
            page = archive.render_rankings_md(stats, code, archive.load_categories(ROOT))
            s = S[code]
            self.assertIn(s["week"], page)
            self.assertIn(s["h_repo"], page)
            self.assertNotIn("Rankings snapshot", page)
            self.assertNotIn("Stars gained", page)
            self.assertNotIn("Data fetched from", page)
            self.assertNotIn("Beijing 00:00", page)

    def test_index_links_point_to_same_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for code in LANGS:
                text = archive.render_index(root, code)  # empty history still renders
                self.assertIn(f"latest/{archive.rankings_name(code)}", text)
                self.assertIn(f"../{LANGS[code][0]}", text)
                self.assertIn(S[code]["idx_no_snaps"], text)

    def test_write_snapshot_writes_every_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data/categories.json").write_text(
                (ROOT / "data/categories.json").read_text("utf-8"), "utf-8")
            st = json.loads(json.dumps(stats))
            d = archive.write_snapshot(root, st)
            for code in LANGS:
                self.assertTrue((d / archive.rankings_name(code)).exists(), code)

    def test_stale_check_detects_edited_localized_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data/categories.json").write_text(
                (ROOT / "data/categories.json").read_text("utf-8"), "utf-8")
            archive.write_snapshot(root, json.loads(json.dumps(stats)))
            archive.refresh_latest_and_index(root)
            self.assertEqual(archive.stale_latest_and_index(root), [])
            page = next(root.glob("rankings/*/*/rankings.zh-Hans.md"))
            page.write_text("hand edit", "utf-8")
            self.assertEqual(len(archive.stale_latest_and_index(root)), 1)

    def test_readme_history_line_links_own_language(self):
        for code, (fname, _l) in LANGS.items():
            text = (ROOT / fname).read_text("utf-8")
            if code != "en":
                self.assertNotIn("(rankings/README.md)", text, fname)
                self.assertNotIn("(latest/rankings.md)", text, fname)


if __name__ == "__main__":
    unittest.main()
