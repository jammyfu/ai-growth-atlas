import datetime as dt
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import archive  # noqa: E402
import update_stars as up  # noqa: E402
import render_readme  # noqa: E402
from i18n import LANGS  # noqa: E402


def utc(y, m, d, h, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=dt.timezone.utc)


def fake_stats(slot, generated_at, names=("a/a", "b/b")):
    projects = []
    for i, n in enumerate(names):
        g = {k: {"window_days": d, "gained": 10 * (i + 1), "effective_days": d,
                 "per_day": round(10 * (i + 1) / d, 3), "young": False}
             for k, d in (("week", 7), ("month", 30), ("year", 365))}
        projects.append({"name": n, "ok": True, "stars": 100 * (i + 1), "growth": g})
    projects.append({"name": "c/gone", "ok": False, "error": "HTTP 404"})
    return {"generated_at": generated_at, "today_utc": generated_at[:10], "slot": slot, "projects": projects}


class SlotTests(unittest.TestCase):
    def test_cn_slot_uses_beijing_date(self):
        s = archive.make_slot(utc(2026, 10, 29, 16, 20), "cn")  # 00:20 on Oct 30 in Beijing
        self.assertEqual((s["id"], s["date"]), ("cn-0000", "2026-10-30"))

    def test_pt_slot_uses_la_date_in_pdt_and_pst(self):
        s = archive.make_slot(utc(2026, 10, 30, 7, 5), "pt")
        self.assertEqual((s["id"], s["date"]), ("pt-0000", "2026-10-30"))
        s = archive.make_slot(utc(2026, 11, 2, 8, 5), "pt")
        self.assertEqual((s["id"], s["date"]), ("pt-0000", "2026-11-02"))

    def test_manual_slot_uses_utc(self):
        s = archive.make_slot(utc(2026, 10, 29, 12, 34), "manual")
        self.assertEqual((s["id"], s["date"]), ("manual-1234", "2026-10-29"))

    def test_auto_detects_from_clock(self):
        self.assertEqual(archive.detect_slot(utc(2026, 10, 29, 16, 3)), "cn")
        self.assertEqual(archive.detect_slot(utc(2026, 10, 29, 7, 3)), "pt")
        self.assertEqual(archive.detect_slot(utc(2026, 10, 29, 12, 0)), "manual")
        self.assertEqual(archive.make_slot(utc(2026, 10, 29, 12, 0))["name"], "manual")

    def test_bad_slot_rejected(self):
        with self.assertRaises(ValueError):
            archive.make_slot(utc(2026, 10, 29, 12), "mars")


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_snapshots_are_kept_per_slot_and_index_links_all(self):
        cn = fake_stats(archive.make_slot(utc(2026, 10, 29, 16, 5), "cn"), "2026-10-29T16:05:00Z")
        pt = fake_stats(archive.make_slot(utc(2026, 10, 30, 7, 5), "pt"), "2026-10-30T07:05:00Z")
        archive.write_snapshot(self.tmp, cn)
        archive.write_snapshot(self.tmp, pt)
        archive.refresh_latest_and_index(self.tmp)
        self.assertTrue((self.tmp / "rankings/2026-10-30/cn-0000/stats.json").exists())
        self.assertTrue((self.tmp / "rankings/2026-10-30/pt-0000/rankings.md").exists())
        index = (self.tmp / "rankings/README.md").read_text("utf-8")
        self.assertIn("2026-10-30/cn-0000/rankings.md", index)
        self.assertIn("2026-10-30/pt-0000/rankings.md", index)
        self.assertLess(index.index("pt-0000"), index.index("(`cn-0000`)"))  # newest first
        latest = json.loads((self.tmp / "latest/stats.json").read_text("utf-8"))
        self.assertEqual(latest["slot"]["id"], "pt-0000")
        self.assertEqual(archive.stale_latest_and_index(self.tmp), [])
        (self.tmp / "latest/rankings.md").write_text("tampered", "utf-8")
        self.assertEqual(archive.stale_latest_and_index(self.tmp), ["latest/rankings.md"])

    def test_rankings_md_is_top_20_and_marks_missing(self):
        names = [f"o/r{i}" for i in range(25)]
        md = archive.render_rankings_md(fake_stats(archive.make_slot(utc(2026, 10, 29, 16), "cn"),
                                                   "2026-10-29T16:00:00Z", names))
        for section in md.split("\n## ")[1:5]:
            self.assertEqual(section.count("\n| 20 |"), 1, section[:40])
            self.assertEqual(section.count("\n| 21 |"), 0)
        self.assertIn("`c/gone`: HTTP 404", md)
        self.assertLess(md.index("## Total stars"), md.index("## Missing data"))

    def test_update_stars_writes_slot_folder(self):
        (self.tmp / "data").mkdir()
        (self.tmp / "data/projects.json").write_text(json.dumps([{"name": "o/r"}]), "utf-8")
        (self.tmp / "data/stars.json").write_text("{}", "utf-8")
        epoch = int(dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc).timestamp())

        def fake(path, token, retries=3):
            if path == "/repos/o/r":
                return {"stargazers_count": 70, "created_at": "2026-10-01T00:00:00Z", "archived": False,
                        "description": "d"}
            return [{"week": epoch, "days": [10] * 7, "total": 70}]

        with mock.patch.object(up, "ROOT", self.tmp), mock.patch.object(up, "api_get", fake), \
                mock.patch.dict("os.environ", {"GITHUB_TOKEN": "t"}):
            rc = up.main(["--slot", "pt", "--now", "2026-10-30T07:05:00Z", "--no-render"])
        self.assertEqual(rc, 0)
        st = json.loads((self.tmp / "rankings/2026-10-30/pt-0000/stats.json").read_text("utf-8"))
        self.assertEqual(st["slot"]["id"], "pt-0000")
        self.assertEqual(st["projects"][0]["stars"], 70)
        self.assertEqual(json.loads((self.tmp / "latest/stats.json").read_text("utf-8")), st)
        self.assertEqual(json.loads((self.tmp / "data/stats.json").read_text("utf-8")), st)
        self.assertEqual(archive.stale_latest_and_index(self.tmp), [])


class RepoHistoryTests(unittest.TestCase):
    def test_committed_snapshots_are_consistent(self):
        snaps = archive.scan_snapshots(ROOT)
        self.assertGreaterEqual(len(snaps), 1)
        index = (ROOT / "rankings/README.md").read_text("utf-8")
        for d, st in snaps:
            self.assertEqual(d.name, st["slot"]["id"])
            self.assertEqual(d.parent.name, st["slot"]["date"])
            self.assertEqual((d / "rankings.md").read_text("utf-8"), archive.render_rankings_md(st))
            self.assertIn(f"{d.parent.name}/{d.name}/rankings.md", index)
            self.assertTrue(all(p["ok"] or "error" in p for p in st["projects"]))

    def test_latest_equals_newest_snapshot_and_matches_data_stats(self):
        newest = archive.scan_snapshots(ROOT)[0][1]
        self.assertEqual(json.loads((ROOT / "latest/stats.json").read_text("utf-8")), newest)
        self.assertEqual(json.loads((ROOT / "data/stats.json").read_text("utf-8")), newest)

    def test_every_readme_links_history_and_latest(self):
        for code, (fname, _l) in LANGS.items():
            text = (ROOT / fname).read_text("utf-8")
            self.assertIn("rankings/README.md", text, fname)
            self.assertIn("latest/rankings.md", text, fname)


if __name__ == "__main__":
    unittest.main()
