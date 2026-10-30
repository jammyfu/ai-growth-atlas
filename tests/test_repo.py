"""Repo-level checks: data schema, generated READMEs, zero telemetry, workflow sanity."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import risers_core as core  # noqa: E402
import archive  # noqa: E402
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
                    self.assertGreater(len(cat_ok), render_readme.README_TOP, f"{fname} {proj['name']} missing curve")

    def test_at_least_20_projects_and_ai_rankings_show_top_10_in_readme_and_20_in_latest(self):
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
                self.assertEqual(len(rows), render_readme.README_TOP, f"{fname} ai/{key}")
            full = (ROOT / "latest" / archive.rankings_name(code)).read_text("utf-8")
            full_block = full.split(f"## {primary['name'][code]}\n", 1)[1].split("\n## ", 1)[0]
            for key in ("week", "month", "year", "total"):
                section = full_block.split(f"### {s[key]}\n", 1)[1].split("\n### ", 1)[0]
                self.assertEqual(len(re.findall(r"^\| \d+ \|", section, flags=re.M)), expect, f"latest {code} ai/{key}")

    def test_english_is_default_readme(self):
        self.assertEqual(LANGS["en"][0], "README.md")
        self.assertIn("star growth", (ROOT / "README.md").read_text("utf-8").lower())

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


class HeadlineTests(unittest.TestCase):
    def test_english_top_has_no_chinese_hint(self):
        body = (ROOT / "README.md").read_text("utf-8").split("\n", 1)[1]  # line 1 is the language switcher
        self.assertNotIn("中文读者", body)
        self.assertNotRegex(body[:1500], r"[\u4e00-\u9fff]")

    def test_every_readme_has_schedule_and_leaders_from_real_data(self):
        primary = next(c for c in cats if c.get("primary"))
        for code, (fname, _l) in LANGS.items():
            s = render_readme.S[code]
            text = (ROOT / fname).read_text("utf-8")
            self.assertIn("UTC+8", s["schedule"])  # the full schedule lives on the how-it-works page
            self.assertIn("America/Los_Angeles", s["schedule"])
            how = (ROOT / "docs" / render_readme.how_name(code)).read_text("utf-8")
            self.assertIn(s["schedule"], how, code)
            self.assertIn(f"docs/{render_readme.how_name(code)}", text, fname)  # README links to it
            sec = text.split(f"## {s['tops_title']}\n", 1)[1].split("\n## ", 1)[0]
            rows = [l for l in sec.splitlines() if l.startswith("| **")]
            self.assertEqual(len(rows), len(cats), fname)
            # AI row first, and its #1 cells are exactly the data-derived leaders
            self.assertIn(primary["name"][code], rows[0])
            ai = [p for p in stats["projects"] if p.get("ok") and p.get("category") == "ai"]
            for key in ("week", "month", "year"):
                self.assertIn(f"[{core.rank(ai, key)[0]['name']}]", rows[0], f"{fname} {key}")
            self.assertIn(f"[{core.rank(ai, 'total')[0]['name']}]", rows[0])
            first_new = stats["newcomers"]["categories"]["ai"]["items"][0]["name"]
            self.assertIn(f"[{first_new}]", rows[0])
            # leaders block sits before the first category section
            self.assertLess(text.index(f"## {s['tops_title']}"), text.index(f"## {primary['name'][code]}\n"))

    def test_titles_mention_the_selling_points(self):
        s = render_readme.S
        self.assertIn("Stars Gained per Day", s["en"]["title"])
        for code in LANG_CODES:
            self.assertTrue(s[code]["title"].startswith("GitHub "), code)
            self.assertTrue(s[code]["title"].endswith("GitHub Risers") or code == "en", code)
        for code in LANG_CODES:
            blob = s[code]["title"] + s[code]["tagline"]
            self.assertIn("AI", blob, code)


class SlimReadmeTests(unittest.TestCase):
    """The README is a first screen plus the boards; explanations live in docs/HOW_IT_WORKS*.md."""

    def readme(self, code):
        return (ROOT / LANGS[code][0]).read_text("utf-8")

    def head(self, code):
        primary = next(c for c in cats if c.get("primary"))
        return self.readme(code).split(f"## {primary['name'][code]}\n", 1)[0]

    def test_first_screen_order_and_nothing_that_moved_out(self):
        for code in LANG_CODES:
            s, text, head = render_readme.S[code], self.readme(code), self.head(code)
            lines = text.splitlines()
            self.assertEqual(lines[0], render_readme.switcher(code), code)  # the language switch stays line 1
            self.assertEqual(lines[2], f"# {s['title']}", code)
            self.assertEqual(len(s["tagline"].splitlines()), 1)
            order = [f"# {s['title']}", render_readme.SOCIAL_IMAGE, "img.shields.io", s["tagline"],
                     render_readme.SITE, f"## {s['tops_title']}", f"## {s['faq_title']}"]
            positions = [head.index(x) for x in order]
            self.assertEqual(positions, sorted(positions), code)
            self.assertLessEqual(len(head.splitlines()), 45, code)
            for gone in (s["intro"], s["schedule"], s["tops_intro"], s["new_intro"], s["method"][0], s["contrib"], "<details>"):
                self.assertNotIn(gone, text, f"{code}: {gone[:40]}")

    def test_title_names_and_english_adds_the_ranking_rule(self):
        S_ = render_readme.S
        self.assertEqual(S_["zh-Hans"]["title"], "GitHub 涨星榜 / GitHub Risers")
        self.assertEqual(S_["zh-Hant"]["title"], "GitHub 漲星榜 / GitHub Risers")
        self.assertIn("ranked by stars gained per day", S_["en"]["title"].lower())

    def test_at_most_three_badges_mit_ci_updated(self):
        for code in LANG_CODES:
            head = self.head(code)
            badges = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", head)
            self.assertEqual(len(badges), 3, code)
            self.assertIn("license-MIT", badges[0])
            self.assertIn("actions/workflows/ci.yml/badge.svg", badges[1])
            self.assertRegex(badges[2], r"badge/updated-\d{4}--\d\d--\d\d-")

    def test_geo_links_are_present_in_every_language(self):
        for code in LANG_CODES:
            text, s = self.readme(code), render_readme.S[code]
            for needle in ("https://jammyfu.github.io/github-risers/", "docs/FAQ.md#what-is-github-risers",
                           "docs/FAQ.md#is-it-the-same-as-github-trending", "docs/FAQ.md#how-often-is-it-updated",
                           "docs/FACTS.md", "CITATION.cff", ".github/social-preview.png", s["website"], s["star_ask"]):
                self.assertIn(needle, text, f"{code}: {needle}")
            for key in ("q1", "q2", "q3"):
                self.assertIn(f"### {s[key]}", text, code)

    def test_faq_links_point_at_real_faq_headings(self):
        faq = (ROOT / "docs/FAQ.md").read_text("utf-8")
        headings = {render_readme.anchor(m) for m in re.findall(r"^## (.+)$", faq, flags=re.M)}
        for code in LANG_CODES:
            for frag in re.findall(r"docs/FAQ\.md#([\w-]+)", self.readme(code)):
                self.assertIn(frag, headings, f"{code}: docs/FAQ.md#{frag}")

    def test_everything_moved_is_on_the_docs_page(self):
        for code in LANG_CODES:
            s = render_readme.S[code]
            how = (ROOT / "docs" / render_readme.how_name(code)).read_text("utf-8")
            for needle in (s["intro"], s["schedule"], s["tops_intro"], s["method"][0], s["contrib"][:30]):
                self.assertIn(render_readme._docs_links(needle), how, f"{code}: {needle[:40]}")

    def test_leader_rows_link_to_existing_category_headings(self):
        for code in LANG_CODES:
            text = self.readme(code)
            headings = {render_readme.anchor(m) for m in re.findall(r"^## (.+)$", text, flags=re.M)}
            links = re.findall(r"\]\(#([^)]+)\)", text)
            self.assertEqual(len(links), len(cats), code)
            for link in links:
                self.assertIn(link, headings, f"{code}: #{link}")

    def test_links_resolve(self):
        pages = [(ROOT / LANGS[c][0], ROOT) for c in LANG_CODES]
        pages += [(ROOT / "docs" / render_readme.how_name(c), ROOT / "docs") for c in LANG_CODES]
        for path, base in pages:
            text = path.read_text("utf-8")
            targets = re.findall(r"\]\(([^)#]+)\)", text) + re.findall(r'src="([^"]+)"', text)
            for target in targets:
                if target.startswith("http"):
                    continue
                self.assertTrue((base / target).exists(), f"{path.name} -> {target}")

    def test_readme_is_much_smaller_than_a_top_20_page(self):
        for code in LANG_CODES:
            self.assertLess(len(self.readme(code).encode("utf-8")), 140_000, code)


class ZeroTelemetryTests(unittest.TestCase):
    def test_no_trackers_in_repo_text(self):
        files = [p for p in ROOT.rglob("*")
                 if p.is_file() and ".git" not in p.parts and p.suffix in {".md", ".py", ".yml", ".yaml", ".json", ".sh", ".html", ".js"}
                 and p.name not in {"test_repo.py"}]
        for f in files:
            body = f.read_text("utf-8", "replace").lower()
            # Inert JSON-LD blocks (structured data for search engines, never executed) are the only allowed <script>.
            body = re.sub(r'<script type="application/ld\+json">.*?</script>', "", body, flags=re.S)
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
