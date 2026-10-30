"""Repo-level checks: data schema, generated READMEs, zero telemetry, workflow sanity."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import risers_core as core  # noqa: E402
import render_readme  # noqa: E402
from i18n import LANGS  # noqa: E402

LANG_CODES = list(LANGS)
projects = json.loads((ROOT / "data/projects.json").read_text("utf-8"))
cats = json.loads((ROOT / "data/categories.json").read_text("utf-8"))
stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))
TRACKERS = ("googletagmanager", "google-analytics", "gtag(", "clarity.ms", "plausible", "umami",
            "matomo", "hotjar", "mixpanel", "segment.com", "<script")


class DataTests(unittest.TestCase):
    def test_projects_have_all_languages_and_valid_category(self):
        ids = {c["id"] for c in cats}
        for p in projects:
            self.assertIn(p["category"], ids, p["name"])
            self.assertEqual(sorted(p["desc"]), sorted(LANG_CODES), p["name"])
            self.assertTrue(all(p["desc"][l].strip() for l in LANG_CODES))
            self.assertNotIn("stars_note", p)  # unverifiable claims are not allowed

    def test_categories_have_all_languages(self):
        for c in cats:
            self.assertEqual(sorted(c["name"]), sorted(LANG_CODES))
            self.assertEqual(sorted(c["desc"]), sorted(LANG_CODES))
            self.assertTrue(c.get("topics"), c["id"])
            self.assertIn("primary", c)
            self.assertIn("order", c)

    def test_stats_cover_every_project_and_are_consistent(self):
        self.assertEqual([p["name"] for p in stats["projects"]], [p["name"] for p in projects])
        for p in stats["projects"]:
            if not p["ok"]:
                self.assertIn("error", p)
                continue
            for key, days in core.WINDOWS.items():
                g = p["growth"][key]
                self.assertEqual(g["window_days"], days)
                self.assertGreaterEqual(g["gained"], 0)
                self.assertLessEqual(g["effective_days"], days)
                self.assertAlmostEqual(g["per_day"], g["gained"] / g["effective_days"], places=2)
            if p["history_complete"]:
                # full history from the API should add up to the current star count;
                # GitHub allows a small edge discrepancy (removed stars / bucket boundaries)
                self.assertLessEqual(abs(p["history_total"] - p["stars"]), 2, p["name"])

    def test_snapshots_have_today(self):
        snaps = json.loads((ROOT / "data/stars.json").read_text("utf-8"))
        for p in stats["projects"]:
            if p["ok"]:
                self.assertEqual(snaps[p["name"]][stats["today_utc"]], p["stars"])


class ReadmeTests(unittest.TestCase):
    def test_generated_readmes_are_current(self):
        self.assertEqual(render_readme.main(["--check"]), 0)

    def test_language_switcher_on_top_of_every_readme(self):
        for code, (fname, label) in LANGS.items():
            head = (ROOT / fname).read_text("utf-8").split("\n", 1)[0]
            for c2, (f2, l2) in LANGS.items():
                self.assertIn(f"**{l2}**" if c2 == code else f"[{l2}]({f2})", head, fname)

    def test_sections_order_total_last_and_curves_everywhere(self):
        primary = next(c for c in cats if c.get("primary"))
        for code, (fname, _l) in LANGS.items():
            text = (ROOT / fname).read_text("utf-8")
            s = render_readme.S[code]
            self.assertIn(f"## {primary['name'][code]}", text, fname)
            block = text.split(f"## {primary['name'][code]}\n", 1)[1].split("\n## ", 1)[0]
            self.assertLess(block.index(f"### {s['week']}"), block.index(f"### {s['total']}"), fname)
            ok_names = {p["name"] for p in stats["projects"] if p.get("ok")}
            for proj in projects:
                if proj["name"] not in ok_names:
                    continue
                if core.star_history_svg(proj["name"]) not in text:
                    cat_ok = [p for p in stats["projects"]
                              if p.get("ok") and p.get("category") == proj["category"]]
                    self.assertGreater(len(cat_ok), 20, f"{fname} {proj['name']} missing curve")

    def test_at_least_20_projects_and_ai_rankings_show_top_20(self):
        self.assertGreaterEqual(len(projects), 20)
        self.assertGreaterEqual(len(cats), 7)
        ids = {c["id"] for c in cats}
        self.assertEqual(ids, {"ai", "devtools", "security", "web", "infra", "design", "data"})
        ai_ok = [p for p in stats["projects"] if p.get("ok") and p.get("category") == "ai"]
        expect = min(20, len(ai_ok))
        self.assertEqual(expect, 20)
        primary = next(c for c in cats if c.get("primary"))
        for code, (fname, _l) in LANGS.items():
            text = (ROOT / fname).read_text("utf-8")
            s = render_readme.S[code]
            block = text.split(f"## {primary['name'][code]}\n", 1)[1].split("\n## ", 1)[0]
            for key in ("week", "month", "year", "total"):
                section = block.split(f"### {s[key]}\n", 1)[1].split("\n### ", 1)[0]
                rows = re.findall(r"^\| \d+ \|", section, flags=re.M)
                self.assertEqual(len(rows), expect, f"{fname} ai/{key}")

    def test_english_is_default_readme(self):
        self.assertEqual(LANGS["en"][0], "README.md")
        self.assertIn("ranked by how fast", (ROOT / "README.md").read_text("utf-8"))

    def test_every_language_translates_every_ui_string(self):
        keys = set(render_readme.S["en"])
        for code in LANG_CODES:
            self.assertEqual(set(render_readme.S[code]), keys, code)
        for code in LANG_CODES:
            if code == "en":
                continue
            s = render_readme.S[code]
            for key, value in s.items():
                if key in ("none", "h_rank", "title"):  # "#" and the project name stay as is
                    continue
                self.assertNotEqual(value, render_readme.S["en"][key], f"{code}.{key} is still English")

    def test_non_english_readmes_have_no_english_image_alt_or_day_units(self):
        for code, (fname, _l) in LANGS.items():
            if code == "en":
                continue
            text = (ROOT / fname).read_text("utf-8")
            self.assertNotIn('alt="star history', text, fname)
            self.assertIsNone(re.search(r"<sub>[^<]*\d\s?d</sub>", text), fname)


class ZeroTelemetryTests(unittest.TestCase):
    def test_no_trackers_in_repo_text(self):
        files = [p for p in ROOT.rglob("*")
                 if p.is_file() and ".git" not in p.parts and p.suffix in {".md", ".py", ".yml", ".yaml", ".json", ".sh", ".html", ".js"}
                 and p.name not in {"test_repo.py"}]
        for f in files:
            body = f.read_text("utf-8", "replace").lower()
            for t in TRACKERS:
                self.assertNotIn(t, body, f"{f.relative_to(ROOT)} contains {t}")


class WorkflowTests(unittest.TestCase):
    def test_daily_workflow_has_schedule_and_least_privilege(self):
        wf = (ROOT / ".github/workflows/daily-update.yml").read_text("utf-8")
        self.assertRegex(wf, r"cron: '\d+ \d+ \* \* \*'")  # exact crons are checked in test_schedule.py
        self.assertIn("workflow_dispatch", wf)
        self.assertIn("contents: write", wf)
        self.assertIn("tools/update_stars.py", wf)
        for line in re.findall(r"uses: (\S+)", wf):
            self.assertTrue(line.startswith("actions/"), line)  # first-party actions only


if __name__ == "__main__":
    unittest.main()
