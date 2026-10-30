"""Suspected cracked / pirated / activator repos: kept, flagged, ranked last, never a category leader.

Also pins that the *scheduled* entry points (GitHub Actions cron slots and the local launchd script)
all go through the same code path: tools/update_stars.py -> newcomers.discover_all ->
newcomers.discover_category (topic requirement + tools/spam.py) -> archive / render_readme.
"""
import datetime as dt
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import archive  # noqa: E402
import newcomers as nc  # noqa: E402
import render_readme  # noqa: E402
import risers_core as core  # noqa: E402
import spam  # noqa: E402
import update_stars as up  # noqa: E402

NOW = dt.datetime(2026, 10, 30, 0, 0, tzinfo=dt.timezone.utc)
NOSLEEP = lambda s: None  # noqa: E731

SPAM_REPOS = [  # real examples seen in the first live run
    ("UniteCuttlefishBolt/Canva-Pro", "Canva Pro 2026: Complete standalone setup with all features unlocked"),
    ("CaretakerPlain/Whale-Tracker", "Whale Tracker 2026: Pre-activated desktop edition"),
    ("ScorpionHub17/KMS-Pico", "Kms Pico Free 2026 complete standalone setup."),
    ("Sourcecladrag/Windows-Optimizer", "Windows Optimizer 2026 - Full working installer with advanced tools"),
    ("petawheelwrightseek/Adobe-Substance-3d", "Creative Studio App 2023: Full working installer"),
    ("megaharmonystable/Adobe-Acrobat-Pro", "Secure PDF Document Processor 2026 complete standalone installation"),
    ("UltraSultanHonor/recon-v1.7.0", "Published: 2026-10-28"),
    ("someone/Photoshop-keygen", ""),
    ("someone/office-activator", ""),
    ("someone/tool-free-download", ""),
    ("someone/Cinema-4d", ""),
]
NORMAL_REPOS = [
    ("adobe/react-spectrum", "A collection of libraries and tools for UI"),
    ("autodesk/forge-viewer-utils", "Helpers"),
    ("nextlevelbuilder/ui-ux-pro-max-skill", "UI/UX design intelligence for AI coding agents"),
    ("o/activation-functions", "Neural network activation function zoo"),
    ("o/patch-package-lite", "Patch your node_modules"),
    ("o/crackle", "A crackling fire sound generator"),
    ("t3dotgg/tstack", "The agent skills I use every day. Works with Claude Code and Codex."),
]


def repo(name, stars, days_old, desc="a normal repo", topics=("ai",), **kw):
    created = (NOW - dt.timedelta(days=days_old)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = {"full_name": name, "id": abs(hash(name)) % 10**8, "html_url": f"https://github.com/{name}",
         "description": desc, "language": "Python", "stargazers_count": stars, "created_at": created,
         "fork": False, "archived": False, "private": False, "topics": list(topics)}
    r.update(kw)
    return r


class DetectionTests(unittest.TestCase):
    def test_known_spam_is_flagged(self):
        for name, desc in SPAM_REPOS:
            with self.subTest(name=name):
                self.assertIsNotNone(spam.suspicious_reason({"full_name": name, "description": desc, "language": None}))

    def test_normal_repos_are_not_flagged(self):
        for name, desc in NORMAL_REPOS:
            with self.subTest(name=name):
                self.assertIsNone(spam.suspicious_reason({"full_name": name, "description": desc, "language": "TypeScript"}))

    def test_tracked_projects_are_clean(self):
        for p in json.loads((ROOT / "data/projects.json").read_text("utf-8")):
            self.assertIsNone(spam.suspicious_reason({"full_name": p["name"], "description": p["desc"]["en"], "language": "x"}),
                              p["name"])


class RankingTests(unittest.TestCase):
    def test_suspicious_ranks_after_every_normal_repo_even_when_hotter(self):
        items = [nc.to_item(r, NOW) for r in (
            repo("a/Canva-Pro", 9000, 1, "Canva Pro 2026: Complete standalone setup"),   # 9000/day
            repo("b/normal-low", 150, 6),
            repo("c/normal-high", 600, 2),
        )]
        ranked = nc.rank_items(items)
        self.assertEqual([i["name"] for i in ranked], ["c/normal-high", "b/normal-low", "a/Canva-Pro"])
        self.assertTrue(ranked[-1]["suspicious"])
        self.assertNotIn("suspicious", ranked[0])

    def _api(self, pool):
        def api(path):
            if path.startswith("/search/repositories"):
                q = parse_qs(urlparse(path).query)["q"][0]
                topic = q.split()[0].removeprefix("topic:")
                hits = [r for r in pool if topic in r["topics"]]
                return {"total_count": len(hits), "items": hits}
            return next(r for r in pool if r["full_name"] == path.removeprefix("/repos/"))
        return api

    def test_discover_category_requires_topic_and_orders_spam_last(self):
        pool = [
            repo("a/Canva-Pro", 9000, 1, "Canva Pro 2026: Complete standalone setup", topics=("ai",)),
            repo("b/real-agent", 300, 3, topics=("ai", "llm")),
            repo("c/no-topic-but-mentions-llm", 5000, 1, "an LLM thing", topics=("misc",)),
        ]
        cat = {"id": "ai", "topics": ["ai", "llm"]}
        res = nc.discover_category(self._api(pool), NOW, cat, set(), NOSLEEP)
        self.assertEqual([i["name"] for i in res["items"]], ["b/real-agent", "a/Canva-Pro"])
        self.assertEqual(res["suspicious_in_board"], 1)

    def test_spam_cannot_crowd_normal_repos_out_of_the_refresh_budget(self):
        pool = [repo(f"s/Spam-{i}", 5000 + i, 1, "Full working installer 2026", topics=("ai",)) for i in range(10)]
        pool.append(repo("n/normal", 120, 4, topics=("ai",)))
        orig = nc.REFRESH_TOP
        nc.REFRESH_TOP = 3
        try:
            res = nc.discover_category(self._api(pool), NOW, {"id": "ai", "topics": ["ai"]}, set(), NOSLEEP)
        finally:
            nc.REFRESH_TOP = orig
        self.assertEqual(res["items"][0]["name"], "n/normal")

    def test_categories_json_is_topic_only(self):
        for c in json.loads((ROOT / "data/categories.json").read_text("utf-8")):
            self.assertTrue(c["topics"], c["id"])
            self.assertNotIn("keywords", c)
            self.assertNotIn("languages", c)
            self.assertFalse({"design", "security", "web", "data", "ui", "javascript", "typescript", "creative"} & set(c["topics"]),
                             f"{c['id']} still lists a generic topic")


class LeaderTests(unittest.TestCase):
    def test_suspicious_is_never_a_leader(self):
        block = {"ok": True, "items": [
            {"name": "n/normal", "url": "u", "per_day": 5.0, "stars": 100},
            {"name": "s/Canva-Pro", "url": "u", "per_day": 999.0, "stars": 9999, "suspicious": "phrase:x"},
        ]}
        stats = {"projects": []}
        self.assertEqual(render_readme.leaders(stats, [], "ai", block)["new"]["name"], "n/normal")
        block["items"] = block["items"][1:]  # only spam left -> no leader at all
        self.assertIsNone(render_readme.leaders(stats, [], "ai", block)["new"])

    def test_committed_data_spam_is_last_and_not_in_leader_table(self):
        st = json.loads((ROOT / "latest/stats.json").read_text("utf-8"))
        readme = (ROOT / "README.md").read_text("utf-8")
        tops = readme[readme.index("## Category leaders"):readme.index("<details>")]
        for cid, block in st["newcomers"]["categories"].items():
            items = block.get("items", [])
            flags = [bool(spam.suspicious_reason({"full_name": i["name"], "description": i["description"],
                                                  "language": i["language"], "topics": i.get("topics")})) for i in items]
            self.assertEqual(flags, sorted(flags), f"{cid}: suspicious repo ranked before a normal one")
            for i, f in zip(items, flags):
                if f:
                    self.assertNotIn(i["name"], tops)

    def test_every_language_marks_and_explains_suspicious_rows(self):
        stats = json.loads((ROOT / "latest/stats.json").read_text("utf-8"))
        cats = archive.load_categories(ROOT)
        block = stats["newcomers"]["categories"]["ai"]
        block["items"] = [dict(block["items"][0], suspicious="phrase:test")] + block["items"][1:3]
        for lang in ("en", "zh-Hans", "zh-Hant", "ja", "ko"):
            md = archive.render_rankings_md(stats, lang, cats)
            self.assertIn("⚠", md)
            self.assertIn("docs/CATEGORIES.md", md)


class ScheduledPathTests(unittest.TestCase):
    """Cron slots and the launchd script must all run the same rules."""

    def test_workflow_and_local_script_run_update_stars(self):
        wf = (ROOT / ".github/workflows/daily-update.yml").read_text("utf-8")
        sh = (ROOT / "tools/local_daily.sh").read_text("utf-8")
        for text in (wf, sh):
            self.assertRegex(text, r"tools/update_stars\.py --slot")
        # both Beijing and both LA cron entries feed the single "update" job that runs update_stars.py
        self.assertEqual(len(re.findall(r"update_stars\.py", wf)), 1)
        for cron in ("'0 16 * * *'", "'0 7 * * *'", "'0 8 * * *'"):
            self.assertIn(cron, wf)
        plists = list((ROOT / "docs/launchd").glob("*.plist"))
        self.assertEqual(len(plists), 2)  # Beijing 00:00 and Los Angeles 00:00
        for pl in plists:
            self.assertIn("local_daily.sh", pl.read_text("utf-8"), pl.name)

    def test_update_stars_uses_the_shared_discovery_and_render(self):
        src = (ROOT / "tools/update_stars.py").read_text("utf-8")
        self.assertIn("newcomers.discover_all(", src)
        self.assertNotIn("discover_category", src)   # no private side path
        self.assertIn("render_readme.main", src)
        disc = (ROOT / "tools/newcomers.py").read_text("utf-8")
        body = disc[disc.index("def discover_category"):disc.index("def discover_all")]
        self.assertIn("has_category_topic", body)
        self.assertIn("spam.suspicious_reason", body)
        self.assertIn("rank_items", body)

    def test_full_update_run_applies_rules_end_to_end(self):
        """update_stars.main with the real discover_all/discover_category and a fake GitHub API."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "data").mkdir()
        (tmp / "data/projects.json").write_text(json.dumps([{
            "name": "o/r", "category": "ai", "url": "https://github.com/o/r",
            "desc": {c: "d" for c in ("en", "zh-Hans", "zh-Hant", "ja", "ko")}}]), "utf-8")
        (tmp / "data/stars.json").write_text("{}", "utf-8")
        cats = json.loads((ROOT / "data/categories.json").read_text("utf-8"))
        small = [dict(c, topics=c["topics"][:2]) for c in cats if c["id"] in ("ai", "devtools")]
        (tmp / "data/categories.json").write_text(json.dumps(small), "utf-8")
        epoch = int(dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc).timestamp())
        pool = [
            repo("x/Adobe-Acrobat-Pro", 9000, 1, "Full working installer 2026", topics=("ai", "cli")),
            repo("y/good-agent", 400, 2, topics=("ai",)),
            repo("z/no-category-topic", 3000, 1, topics=("misc",)),
            repo("w/good-cli", 300, 3, topics=("cli",)),
        ]

        def fake(path, token, retries=3):
            if path.startswith("/search/repositories"):
                topic = parse_qs(urlparse(path).query)["q"][0].split()[0].removeprefix("topic:")
                hits = [r for r in pool if topic in r["topics"]]
                return {"total_count": len(hits), "items": hits}
            if "/stargazers/history" in path:
                return [{"week": epoch, "days": [10] * 7, "total": 70}]
            if path == "/repos/o/r":
                return {"stargazers_count": 70, "created_at": "2026-10-01T00:00:00Z", "archived": False, "description": "d"}
            if path.startswith("/repos/"):
                return next(r for r in pool if r["full_name"] == path.removeprefix("/repos/"))
            return [{"week": epoch, "days": [10] * 7, "total": 70}]

        real = nc.discover_all
        with mock.patch.object(up, "ROOT", tmp), mock.patch.object(up, "api_get", fake), \
                mock.patch.object(up.newcomers, "discover_all",
                                  side_effect=lambda *a, **k: real(*a, sleep=NOSLEEP, **k)), \
                mock.patch.dict("os.environ", {"GITHUB_TOKEN": "t"}):
            rc = up.main(["--slot", "cn", "--now", "2026-10-30T00:00:00Z", "--no-render"])
        self.assertEqual(rc, 0)
        st = json.loads((tmp / "rankings/2026-10-30/cn-0000/stats.json").read_text("utf-8"))
        ai = [i["name"] for i in st["newcomers"]["categories"]["ai"]["items"]]
        dev = [i["name"] for i in st["newcomers"]["categories"]["devtools"]["items"]]
        self.assertEqual(ai, ["y/good-agent", "x/Adobe-Acrobat-Pro"])      # spam kept, last; no-topic repo gone
        self.assertEqual(dev, ["w/good-cli"])                             # spam already claimed by AI
        self.assertNotIn("z/no-category-topic", ai + dev)
        self.assertTrue(st["newcomers"]["categories"]["ai"]["items"][1]["suspicious"])
        leader = render_readme.leaders(st, [], "ai", st["newcomers"]["categories"]["ai"])
        self.assertEqual(leader["new"]["name"], "y/good-agent")


if __name__ == "__main__":
    unittest.main()
