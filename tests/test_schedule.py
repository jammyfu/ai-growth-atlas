import datetime as dt
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import schedule_guard as sg  # noqa: E402

LA = "America/Los_Angeles"


def utc(y, m, d, h, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=dt.timezone.utc)


class LocalHourTests(unittest.TestCase):
    def test_pdt_midnight_is_0700_utc(self):  # PDT = UTC-7
        self.assertTrue(sg.is_local_hour(utc(2026, 10, 29, 7), LA, 0))
        self.assertTrue(sg.is_local_hour(utc(2026, 10, 29, 7, 59), LA, 0))
        self.assertFalse(sg.is_local_hour(utc(2026, 10, 29, 8), LA, 0))  # 01:00 PDT

    def test_pst_midnight_is_0800_utc(self):  # PST = UTC-8
        self.assertTrue(sg.is_local_hour(utc(2026, 12, 15, 8), LA, 0))
        self.assertFalse(sg.is_local_hour(utc(2026, 12, 15, 7), LA, 0))  # 23:00 PST the day before

    def test_dst_boundaries_2026(self):
        # spring forward Sun 2026-03-08 10:00 UTC (02:00 PST -> 03:00 PDT)
        self.assertTrue(sg.is_local_hour(utc(2026, 3, 8, 8), LA, 0))      # still PST: 00:00
        self.assertFalse(sg.is_local_hour(utc(2026, 3, 8, 7), LA, 0))     # 23:00 PST on Mar 7
        self.assertTrue(sg.is_local_hour(utc(2026, 3, 9, 7), LA, 0))      # PDT from here on
        # fall back Sun 2026-11-01 09:00 UTC (02:00 PDT -> 01:00 PST)
        self.assertTrue(sg.is_local_hour(utc(2026, 11, 1, 7), LA, 0))     # 00:00 PDT
        self.assertFalse(sg.is_local_hour(utc(2026, 11, 1, 8), LA, 0))    # 01:00 PDT
        self.assertTrue(sg.is_local_hour(utc(2026, 11, 2, 8), LA, 0))     # 00:00 PST

    def test_exactly_one_la_slot_passes_every_day_of_the_year(self):
        day = dt.date(2026, 1, 1)
        while day.year == 2026:
            passes = [h for h in (7, 8) if sg.is_local_hour(utc(day.year, day.month, day.day, h), LA, 0)]
            self.assertEqual(len(passes), 1, f"{day}: {passes}")
            day += dt.timedelta(days=1)

    def test_beijing_slot_is_1600_utc_all_year(self):
        for month in (1, 4, 7, 10):
            self.assertTrue(sg.is_local_hour(utc(2026, month, 15, 16), "Asia/Shanghai", 0))
            self.assertFalse(sg.is_local_hour(utc(2026, month, 15, 15), "Asia/Shanghai", 0))

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            sg.local_hour(dt.datetime(2026, 10, 29, 7), LA)


class CliTests(unittest.TestCase):
    def run_guard(self, now):
        return subprocess.run([sys.executable, str(ROOT / "tools/schedule_guard.py"), "--tz", LA,
                               "--hour", "0", "--now", now], capture_output=True, text=True)

    def test_exit_codes(self):
        run = self.run_guard("2026-10-29T07:05:00Z")
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertIn("run:", run.stdout)
        skip = self.run_guard("2026-10-29T08:05:00Z")
        self.assertEqual(skip.returncode, 1)
        self.assertIn("skip:", skip.stdout)


class LocalScriptTests(unittest.TestCase):
    def run_script(self, now, slot):
        env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}
        env["ATLAS_NOW_UTC"] = now
        return subprocess.run(["bash", str(ROOT / "tools/local_daily.sh"), "--slot", slot],
                              capture_output=True, text=True, env=env, cwd=ROOT)

    def test_la_slot_skips_outside_midnight_without_touching_anything(self):
        r = self.run_script("2026-10-29T08:30:00Z", "la")  # 01:30 PDT
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("skip:", r.stdout)
        self.assertNotIn("error", r.stderr)

    def test_beijing_slot_skips_outside_midnight(self):
        r = self.run_script("2026-10-29T15:30:00Z", "beijing")  # 23:30 Beijing
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("skip:", r.stdout)

    def test_unknown_slot_rejected(self):
        r = self.run_script("2026-10-29T07:30:00Z", "mars")
        self.assertEqual(r.returncode, 2)


class WorkflowScheduleTests(unittest.TestCase):
    wf = (ROOT / ".github/workflows/daily-update.yml").read_text("utf-8")

    def test_three_crons(self):
        crons = re.findall(r"- cron: '([^']+)'", self.wf)
        self.assertEqual(sorted(crons), sorted(["0 16 * * *", "0 7 * * *", "0 8 * * *"]))

    def test_la_guard_wired_and_steps_gated(self):
        self.assertIn("tools/schedule_guard.py --tz America/Los_Angeles --hour 0", self.wf)
        self.assertEqual(self.wf.count("if: steps.gate.outputs.run == 'true'"), 3)
        # Beijing cron is the only unguarded schedule
        self.assertIn('"$CRON" != "0 16 * * *"', self.wf)


if __name__ == "__main__":
    unittest.main()
