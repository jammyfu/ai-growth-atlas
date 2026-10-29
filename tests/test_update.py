import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import update_stars as up  # noqa: E402

TODAY = dt.date(2026, 10, 29)


def epoch(d):
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


class FetchTests(unittest.TestCase):
    def test_fetch_project_ok_reads_only_github_endpoints(self):
        calls = []

        def fake(path, token, retries=3):
            calls.append(path)
            if path == "/repos/o/r":
                return {"stargazers_count": 70, "created_at": "2026-10-01T00:00:00Z", "archived": False,
                        "description": "d"}
            if "stargazers/history" in path:
                return [{"week": epoch(dt.date(2026, 10, 25)), "days": [10, 10, 10, 10, 10, 10, 10], "total": 70}]
            raise AssertionError(path)

        with mock.patch.object(up, "api_get", fake):
            r = up.fetch_project("o/r", "t", TODAY, {})
        self.assertTrue(r["ok"])
        self.assertEqual(r["stars"], 70)
        self.assertTrue(r["history_complete"])
        self.assertEqual(r["history_total"], 70)
        self.assertEqual(r["growth"]["week"]["gained"], 40)  # 10-25..10-28
        self.assertTrue(r["growth"]["year"]["young"])
        self.assertTrue(all(c.startswith("/repos/o/r") for c in calls))

    def test_fetch_project_marks_missing_instead_of_guessing(self):
        def fake(path, token, retries=3):
            raise up.GitHubError(404, "Not Found")

        with mock.patch.object(up, "api_get", fake):
            r = up.fetch_project("o/gone", "t", TODAY, {})
        self.assertFalse(r["ok"])
        self.assertIn("404", r["error"])
        self.assertNotIn("stars", r)

    def test_history_paginates_until_year_covered(self):
        def page(n):
            start = TODAY - dt.timedelta(weeks=30 * (n - 1))
            return [{"week": epoch(start - dt.timedelta(weeks=i)), "days": [0] * 7, "total": 0} for i in range(30)]

        seen = []

        def fake(path, token, retries=3):
            n = int(path.rsplit("page=", 1)[1])
            seen.append(n)
            return page(n)

        with mock.patch.object(up, "api_get", fake):
            pages, complete = up.fetch_history_pages("o/r", "t", TODAY)
        self.assertEqual(seen, [1, 2])  # 60 weeks > 52 weeks needed
        self.assertFalse(complete)
        self.assertEqual(len(pages), 2)


if __name__ == "__main__":
    unittest.main()
