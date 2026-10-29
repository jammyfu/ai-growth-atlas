import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import archive  # noqa: E402
import atlas_core as core  # noqa: E402
import newcomers as nc  # noqa: E402
import render_readme  # noqa: E402
from i18n import LANGS, S  # noqa: E402

NOW = dt.datetime(2026, 10, 30, 0, 0, tzinfo=dt.timezone.utc)
NOSLEEP = lambda s: None  # noqa: E731


def repo(name, stars, days_old, **kw):
    created = (NOW - dt.timedelta(days=days_old)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = {"full_name": name, "id": abs(hash(name)) % 10**8, "html_url": f"https://github.com/{name}",
         "description": kw.pop("description", f"{name} desc"), "language": "Python",
         "stargazers_count": stars, "created_at": created, "fork": False, "archived": False, "private": False}
    r.update(kw)
    return r


class FilterTests(unittest.TestCase):
    def test_queries_use_window_min_stars_and_no_forks(self):
        qs = nc.build_queries(NOW)
        self.assertEqual(len(qs), len(nc.AI_TOPICS) + len(nc.AI_KEYWORDS))
        for _label, q in qs:
            self.assertIn("created:>=2026-10-23T00:00:00Z", q)
            self.assertIn("stars:>=100", q)
            self.assertIn("fork:false", q)
            self.assertIn("archived:false", q)

    def test_qualifies_window_edges_forks_archived_stars(self):
        self.assertTrue(nc.qualifies(repo("a/a", 100, 6.9), NOW))
        self.assertFalse(nc.qualifies(repo("a/a", 100, 7.1), NOW))      # older than 7 days
        self.assertFalse(nc.qualifies(repo("a/a", 99, 1), NOW))         # too few stars
        self.assertFalse(nc.qualifies(repo("a/a", 500, 1, fork=True), NOW))
        self.assertFalse(nc.qualifies(repo("a/a", 500, 1, archived=True), NOW))
        self.assertFalse(nc.qualifies(repo("a/a", 500, -1), NOW))       # created in the future

    def test_hotness_is_stars_per_day_with_one_day_floor(self):
        self.assertEqual(nc.to_item(repo("a/a", 500, 0.1), NOW)["per_day"], 500.0)  # floor: 1 day
        self.assertEqual(nc.to_item(repo("a/a", 600, 3), NOW)["per_day"], 200.0)

    def test_description_is_made_safe_for_a_table_cell(self):
        tag = "<scr" + "ipt>"
        d = nc.clean_description("a | b\n" + tag + "x  & c")
        self.assertNotIn("|", d)
        self.assertNotIn("\n", d)
        self.assertNotIn(tag, d)
        self.assertEqual(len(nc.clean_description("x" * 500)), nc.DESC_MAX)
        self.assertEqual(nc.clean_description(None), "")


class DedupeTests(unittest.TestCase):
    def test_excludes_tracked_and_displayed_case_insensitively(self):
        items = [nc.to_item(repo(n, 300, 2), NOW) for n in ("Tracked/Repo", "new/one")]
        kept, dropped = nc.exclude_duplicates(items, {"tracked/repo"})
        self.assertEqual([i["name"] for i in kept], ["new/one"])
        self.assertEqual(dropped, ["Tracked/Repo"])

    def test_same_repo_from_several_queries_kept_once(self):
        it = nc.to_item(repo("new/one", 300, 2), NOW)
        kept, _ = nc.exclude_duplicates([it, dict(it), dict(it, name="NEW/ONE")], set())
        self.assertEqual(len(kept), 1)

    def test_overlap_detector_flags_shared_projects(self):
        projects = [{"name": "t/one", "ok": True, "stars": 5,
                     "growth": {k: {"per_day": 1.0} for k in ("week", "month", "year")}}]
        self.assertEqual(nc.overlap_with_rankings([{"name": "T/One"}], projects, 20, core.rank), {"T/One"})
        self.assertEqual(nc.overlap_with_rankings([{"name": "x/y"}], projects, 20, core.rank), set())


class DiscoverTests(unittest.TestCase):
    def fake_api(self, fail_all=False):
        pool = {
            "ai": [repo("new/hot", 900, 1.5), repo("new/warm", 400, 4), repo("tracked/proj", 5000, 2)],
            "llm": [repo("new/hot", 900, 1.5), repo("old/thing", 9000, 20), repo("new/fork", 800, 1, fork=True)],
        }

        def api(path):
            if path.startswith("/search/repositories"):
                if fail_all:
                    raise RuntimeError("HTTP 403: rate limited")
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(path).query)["q"][0]
                for t, items in pool.items():
                    if q.startswith(f"topic:{t} "):
                        return {"total_count": len(items), "items": items}
                return {"total_count": 0, "items": []}
            name = path.removeprefix("/repos/")
            for items in pool.values():
                for r in items:
                    if r["full_name"] == name:
                        return dict(r, stargazers_count=r["stargazers_count"] + 100)  # fresher count
            raise RuntimeError("404")
        return api

    def test_discover_ranks_dedupes_and_refreshes(self):
        res = nc.discover(self.fake_api(), NOW, {"tracked/proj"}, sleep=NOSLEEP)
        self.assertTrue(res["ok"])
        names = [i["name"] for i in res["items"]]
        self.assertEqual(names, ["new/hot", "new/warm"])           # fork/old/tracked gone, ranked by per_day
        self.assertEqual(res["items"][0]["stars"], 1000)           # refreshed via /repos/{r}
        self.assertEqual(res["excluded_duplicates"], ["tracked/proj"])
        self.assertEqual(len(set(names)), len(names))
        self.assertEqual(sum(1 for q in res["queries"] if not q["ok"]), 0)

    def test_total_search_failure_is_reported_not_estimated(self):
        res = nc.discover(self.fake_api(fail_all=True), NOW, set(), sleep=NOSLEEP)
        self.assertFalse(res["ok"])
        self.assertEqual(res["items"], [])
        self.assertIn("rate limited", res["error"])

    def test_top_20_cap(self):
        many = [repo(f"n/r{i}", 200 + i, 2) for i in range(30)]
        api = lambda p: ({"total_count": 30, "items": many} if p.startswith("/search") else None)  # noqa: E731
        orig = nc.REFRESH_TOP
        nc.REFRESH_TOP = 100
        try:
            def api2(p):
                if p.startswith("/search"):
                    return {"total_count": 30, "items": many}
                return next(r for r in many if r["full_name"] == p.removeprefix("/repos/"))
            res = nc.discover(api2, NOW, set(), sleep=NOSLEEP)
        finally:
            nc.REFRESH_TOP = orig
        self.assertEqual(len(res["items"]), 20)


class RepoNewcomersTests(unittest.TestCase):
    stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))
    projects = json.loads((ROOT / "data/projects.json").read_text("utf-8"))

    def test_real_data_meets_every_criterion(self):
        new = self.stats["newcomers"]
        self.assertTrue(new["ok"], new.get("error"))
        gen = nc.parse_ts(self.stats["generated_at"])
        items = new["items"]
        self.assertLessEqual(len(items), 20)
        self.assertGreater(len(items), 0)
        for it in items:
            age = (gen - nc.parse_ts(it["created_at"])).total_seconds() / 86400
            self.assertLessEqual(age, 7.01, it["name"])
            self.assertGreaterEqual(it["stars"], nc.MIN_STARS)
        per_day = [i["per_day"] for i in items]
        self.assertEqual(per_day, sorted(per_day, reverse=True))

    def test_no_project_is_in_two_rankings(self):
        items = self.stats["newcomers"]["items"]
        names = [i["name"].lower() for i in items]
        self.assertEqual(len(names), len(set(names)))
        tracked = {p["name"].lower() for p in self.projects}
        self.assertEqual(set(names) & tracked, set())
        self.assertEqual(nc.overlap_with_rankings(items, self.stats["projects"], 20, core.rank), set())

    def test_every_snapshot_has_no_overlap(self):
        for _d, st in archive.scan_snapshots(ROOT):
            new = st.get("newcomers")
            if new and new.get("ok"):
                self.assertEqual(nc.overlap_with_rankings(new["items"], st["projects"], 20, core.rank), set(),
                                 st["slot"]["id"])


class ReadmeNewcomersTests(unittest.TestCase):
    stats = json.loads((ROOT / "data/stats.json").read_text("utf-8"))

    def test_every_language_has_the_ranking_with_all_items_and_no_duplicates(self):
        items = self.stats["newcomers"]["items"]
        for code, (fname, _l) in LANGS.items():
            text = (ROOT / fname).read_text("utf-8")
            s = S[code]
            heads = re.findall(r"^## (.+)$", text, flags=re.M)
            self.assertIn(s["new"], heads, fname)
            self.assertLess(heads.index(s["new"]), heads.index(s["week"]))
            self.assertLess(heads.index(s["year"]), heads.index(s["total"]))
            section = text.split(f"## {s['new']}\n", 1)[1].split("\n## ", 1)[0]
            rows = re.findall(r"^\| \d+ \|", section, flags=re.M)
            self.assertEqual(len(rows), len(items), fname)
            for it in items:
                self.assertEqual(section.count(f"]({it['url']})"), 1, f"{fname} {it['name']}")
            self.assertIn("docs/NEW_ARRIVALS.md", section)

    def test_archive_markdown_has_new_section_only_when_present(self):
        slot = archive.make_slot(NOW, "cn")
        base = {"generated_at": "2026-10-30T00:00:00Z", "today_utc": "2026-10-30", "slot": slot, "projects": []}
        self.assertNotIn("Hottest new repos", archive.render_rankings_md(base))
        md = archive.render_rankings_md(dict(base, newcomers={
            "ok": True, "queries": [], "items": [nc.to_item(repo("n/r", 300, 2), NOW)]}))
        self.assertIn("Hottest new repos", md)
        self.assertIn("[n/r](https://github.com/n/r)", md)
        md = archive.render_rankings_md(dict(base, newcomers={"ok": False, "error": "boom", "queries": [], "items": []}))
        self.assertIn("boom", md)


class DocsTests(unittest.TestCase):
    def test_criteria_doc_matches_code(self):
        doc = (ROOT / "docs/NEW_ARRIVALS.md").read_text("utf-8")
        for t in nc.AI_TOPICS:
            self.assertIn(f"`{t}`", doc)
        self.assertIn(f"{nc.MIN_STARS} stars", doc)
        self.assertIn(f"{nc.WINDOW_DAYS} days", doc)
        self.assertIn("deduplication", doc.lower())


if __name__ == "__main__":
    unittest.main()
