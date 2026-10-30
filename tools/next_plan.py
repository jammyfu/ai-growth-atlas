#!/usr/bin/env python3
"""Roll CURRENT_PLAN.md forward, or validate it (harness: CoderSkills continuous-project-loop).

  python3 tools/next_plan.py           if every task is checked, start the next plan from TODO_BACKLOG.md "Now"
  python3 tools/next_plan.py --check   validate CURRENT_PLAN.md against the planning rules; exit 1 if it breaks them

Rolling rewrites CURRENT_PLAN.md only when the current plan is complete and the backlog has items.
The generated plan is a draft: keep one Goal, 3-7 tasks, and edit by hand before continuing.
Planning rules checked: one Plan ID, one Goal, In Scope, Out of Scope, 3-7 verifiable tasks,
a Verification section naming `python3 tools/verify.py`, and Next Candidates.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SECTIONS = ("Plan ID", "Goal", "In Scope", "Out of Scope", "Tasks", "Verification", "Next Candidates")
MIN_TASKS, MAX_TASKS = 3, 7


def section(text: str, name: str) -> str | None:
    m = re.search(rf"^## {re.escape(name)}[ \t]*\n(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    return m.group(1).strip() if m else None


def check_plan(text: str) -> list[str]:
    """Return the list of planning-rule violations (empty = the plan is fine)."""
    problems = [f"missing section: ## {s}" for s in REQUIRED_SECTIONS if section(text, s) is None]
    pid = section(text, "Plan ID")
    if pid is not None and not re.fullmatch(r"PLAN-\d{3,}", pid):
        problems.append("Plan ID must look like PLAN-001")
    goal = section(text, "Goal")
    if goal is not None and (not goal or len([ln for ln in goal.splitlines() if ln.strip()]) > 3):
        problems.append("Goal must be one short paragraph (at most 3 lines)")
    if goal and goal.startswith("DRAFT"):
        problems.append("Goal still says DRAFT: edit the generated plan by hand")
    tasks_body = section(text, "Tasks")
    if tasks_body is not None:
        tasks = re.findall(r"^- \[[ x]\] .+$", tasks_body, flags=re.M)
        if not MIN_TASKS <= len(tasks) <= MAX_TASKS:
            problems.append(f"Tasks must have {MIN_TASKS}-{MAX_TASKS} checkbox items, found {len(tasks)}")
    verification = section(text, "Verification")
    if verification is not None and "tools/verify.py" not in verification:
        problems.append("Verification must name python3 tools/verify.py")
    return problems


def roll(root: Path) -> str:
    plan = (root / "CURRENT_PLAN.md").read_text("utf-8")
    tasks = re.findall(r"^- \[( |x)\] .+$", section(plan, "Tasks") or plan, flags=re.M)
    if tasks and any(t == " " for t in tasks):
        return "CURRENT_PLAN.md still has open tasks; not rolling forward."
    backlog = (root / "TODO_BACKLOG.md").read_text("utf-8")
    m = re.search(r"^## Now\n(.*?)(?=^## |\Z)", backlog, flags=re.M | re.S)
    items = re.findall(r"^- \[ \] (.+)$", m.group(1), flags=re.M) if m else []
    if not items:
        return "Backlog 'Now' is empty; leaving CURRENT_PLAN.md as is."
    m_id = re.search(r"PLAN-(\d+)", plan)
    n = int(m_id.group(1)) + 1 if m_id else 1
    body = "\n".join(f"- [ ] {t}" for t in items[:MAX_TASKS])
    (root / "CURRENT_PLAN.md").write_text(
        f"# CURRENT_PLAN.md\n\n## Plan ID\n\nPLAN-{n:03d}\n\n## Goal\n\nDRAFT: {items[0]}\n\n"
        f"## In Scope\n\n- Items from TODO_BACKLOG.md 'Now'\n\n## Out of Scope\n\n- Everything else\n\n"
        f"## Tasks\n\n{body}\n\n## Verification\n\n- `python3 tools/verify.py`\n\n## Next Candidates\n\n- See TODO_BACKLOG.md\n",
        "utf-8")
    return f"Wrote draft PLAN-{n:03d} with {min(len(items), MAX_TASKS)} task(s). Edit before continuing."


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="validate CURRENT_PLAN.md instead of rolling it")
    args = ap.parse_args(argv)
    if args.check:
        problems = check_plan((root / "CURRENT_PLAN.md").read_text("utf-8"))
        for p in problems:
            print(f"CURRENT_PLAN.md: {p}", file=sys.stderr)
        print("CURRENT_PLAN.md follows the planning rules." if not problems else "CURRENT_PLAN.md breaks the planning rules.")
        return 1 if problems else 0
    print(roll(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
