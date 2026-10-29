import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import atlas_core as core  # noqa: E402

D = dt.date


def week_epoch(d: dt.date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


class HistoryTests(unittest.TestCase):
    def test_history_to_daily_maps_days_from_sunday(self):
        sunday = D(2026, 10, 25)
        pages = [[{"week": week_epoch(sunday), "days": [1, 2, 3, 4, 5, 0, 0], "total": 15}]]
        daily = core.history_to_daily(pages)
        self.assertEqual(daily[D(2026, 10, 25)], 1)
        self.assertEqual(daily[D(2026, 10, 29)], 5)
        self.assertEqual(sum(daily.values()), 15)

    def test_window_excludes_today_and_older(self):
        daily = {D(2026, 10, 29): 100, D(2026, 10, 28): 7, D(2026, 10, 22): 3, D(2026, 10, 21): 50}
        # last 7 complete days before 10-29 are 10-22..10-28
        self.assertEqual(core.window_gain(daily, D(2026, 10, 29), 7), 10)

    def test_effective_days_young_and_old(self):
        today = D(2026, 10, 29)
        self.assertEqual(core.effective_days("2026-10-19T00:00:00Z", today, 30), (10, True))
        self.assertEqual(core.effective_days("2025-01-01T00:00:00Z", today, 30), (30, False))
        # created today -> divisor floors at 1
        self.assertEqual(core.effective_days("2026-10-29T01:00:00Z", today, 7), (1, True))

    def test_compute_growth_per_day(self):
        today = D(2026, 10, 29)
        daily = {today - dt.timedelta(days=i): 10 for i in range(1, 400)}
        g = core.compute_growth(daily, "2020-01-01T00:00:00Z", today)
        self.assertEqual(g["week"]["gained"], 70)
        self.assertEqual(g["week"]["per_day"], 10.0)
        self.assertEqual(g["year"]["gained"], 3650)
        self.assertFalse(g["year"]["young"])

    def test_snapshot_delta(self):
        today = D(2026, 10, 29)
        snaps = {"2026-10-22": 900}
        self.assertEqual(core.snapshot_delta(snaps, today, 7, 1000), {"since": "2026-10-22", "delta": 100})
        self.assertIsNone(core.snapshot_delta(snaps, today, 30, 1000))


class RankTests(unittest.TestCase):
    def mk(self, name, stars, per_day):
        return {"name": name, "ok": True, "stars": stars,
                "growth": {"week": {"per_day": per_day}, "month": {"per_day": 0}, "year": {"per_day": 0}}}

    def test_rank_by_growth_and_total_skips_missing(self):
        ps = [self.mk("a/a", 10, 1.0), self.mk("b/b", 5, 9.0), {"name": "c/c", "ok": False, "error": "x"}]
        self.assertEqual([p["name"] for p in core.rank(ps, "week")], ["b/b", "a/a"])
        self.assertEqual([p["name"] for p in core.rank(ps, "total")], ["a/a", "b/b"])


if __name__ == "__main__":
    unittest.main()
