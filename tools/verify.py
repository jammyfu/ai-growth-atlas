#!/usr/bin/env python3
"""Single verification entry point (harness convention). Uses explicit interpreter paths,
no shell and no PATH lookups, so it also works under cron/launchd.

Steps: compile all Python, run unit tests, check generated READMEs are current.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def commands(root: Path) -> list[list[str]]:
    py = sys.executable
    return [
        [py, "-m", "compileall", "-q", "tools", "tests"],
        [py, "-m", "unittest", "discover", "-s", "tests", "-v"],
        [py, "tools/render_readme.py", "--check"],
    ]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for cmd in commands(root):
        print(">>>", " ".join(cmd), flush=True)
        rc = subprocess.run(cmd, cwd=root).returncode
        if rc != 0:
            print(f"verification failed: {' '.join(cmd)}", file=sys.stderr)
            return rc
    print("All verification commands passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
