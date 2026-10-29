#!/usr/bin/env python3
"""Exit 0 when the current local hour in a time zone equals --hour, else exit 1.

Why: GitHub cron is UTC-only. America/Los_Angeles midnight is 07:00 UTC during PDT and 08:00 UTC
during PST, so the workflow schedules both and this guard lets exactly one of them proceed.

  python3 tools/schedule_guard.py --tz America/Los_Angeles --hour 0
  python3 tools/schedule_guard.py --tz America/Los_Angeles --hour 0 --now 2026-11-02T08:00:00Z   # for tests
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo


def local_hour(now_utc: dt.datetime, tz: str) -> int:
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    return now_utc.astimezone(ZoneInfo(tz)).hour


def is_local_hour(now_utc: dt.datetime, tz: str, hour: int) -> bool:
    return local_hour(now_utc, tz) == hour


def parse_now(value: str | None) -> dt.datetime:
    if not value:
        return dt.datetime.now(dt.timezone.utc)
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tz", required=True)
    ap.add_argument("--hour", type=int, required=True)
    ap.add_argument("--now", default=os.environ.get("ATLAS_NOW_UTC"),
                    help="override current time (ISO 8601, UTC); also read from ATLAS_NOW_UTC")
    args = ap.parse_args(argv)
    now = parse_now(args.now)
    h = local_hour(now, args.tz)
    if h == args.hour:
        print(f"run: {now:%Y-%m-%d %H:%M}Z is {args.hour:02d}:xx in {args.tz}")
        return 0
    print(f"skip: {now:%Y-%m-%d %H:%M}Z is {h:02d}:xx in {args.tz}, not {args.hour:02d}:xx")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
