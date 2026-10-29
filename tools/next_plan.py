#!/usr/bin/env python3
"""Roll CURRENT_PLAN.md forward: if every task is checked, start the next plan from TODO_BACKLOG.md "Now".

Prints the decision; rewrites CURRENT_PLAN.md only when the current plan is complete and the backlog has items.
The generated plan is a draft: keep one Goal, 3-7 tasks, and edit by hand before continuing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    plan = (ROOT / "CURRENT_PLAN.md").read_text("utf-8")
    tasks = re.findall(r"^- \[( |x)\] .+$", plan, flags=re.M)
    if tasks and any(t == " " for t in tasks):
        print("CURRENT_PLAN.md still has open tasks; not rolling forward.")
        return 0
    backlog = (ROOT / "TODO_BACKLOG.md").read_text("utf-8")
    m = re.search(r"^## Now\n(.*?)(?=^## |\Z)", backlog, flags=re.M | re.S)
    items = re.findall(r"^- \[ \] (.+)$", m.group(1), flags=re.M) if m else []
    if not items:
        print("Backlog 'Now' is empty; leaving CURRENT_PLAN.md as is.")
        return 0
    m_id = re.search(r"PLAN-(\d+)", plan)
    n = int(m_id.group(1)) + 1 if m_id else 1
    body = "\n".join(f"- [ ] {t}" for t in items[:7])
    (ROOT / "CURRENT_PLAN.md").write_text(
        f"# CURRENT_PLAN.md\n\n## Plan ID\n\nPLAN-{n:03d}\n\n## Goal\n\nDRAFT: {items[0]}\n\n"
        f"## In Scope\n\n- Items from TODO_BACKLOG.md 'Now'\n\n## Out of Scope\n\n- Everything else\n\n"
        f"## Tasks\n\n{body}\n\n## Verification\n\n- `python3 tools/verify.py`\n\n## Next Candidates\n\n- See TODO_BACKLOG.md\n",
        "utf-8")
    print(f"Wrote draft PLAN-{n:03d} with {min(len(items), 7)} task(s). Edit before continuing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
