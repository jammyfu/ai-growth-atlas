"""Harness regression tests (jammyfu/CoderSkills: continuous-project-loop, multi-project-program-management).

Guards the loop files, the plan shape, plan rolling, and that verify / local-daily do not depend on PATH.
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import next_plan  # noqa: E402
import verify  # noqa: E402

HARNESS_FILES = [
    "AGENTS.md", "PROJECT_BRIEF.md", "MASTER_PLAN.md", "CURRENT_PLAN.md", "TODO_BACKLOG.md",
    "docs/project-governance/WORKLOG.md", "docs/project-governance/DECISIONS.md",
    "docs/project-governance/ACCEPTANCE.md", "docs/project-governance/CHANGELOG.md",
    "docs/AUTOMATION_COMMANDS.md", "docs/LONG_RUNNING_AUTONOMY.md", "tools/verify.py", "tools/next_plan.py",
]
GOOD_PLAN = """# CURRENT_PLAN.md

## Plan ID

PLAN-007

## Goal

One clear goal.

## In Scope

- a

## Out of Scope

- b

## Tasks

- [x] one
- [x] two
- [x] three

## Verification

- `python3 tools/verify.py`

## Next Candidates

- c
"""


# The daily job (Actions schedule / workflow_dispatch, or tools/local_daily.sh) must never be blocked by a
# documentation state; the doc checks still run in CI on every pull request and push.
IN_DAILY_RUN = os.environ.get("GITHUB_EVENT_NAME") in ("schedule", "workflow_dispatch") or bool(os.environ.get("RISERS_DAILY_RUN"))
doc_checks = unittest.skipIf(IN_DAILY_RUN, "doc-state checks are skipped inside the daily data run")


@doc_checks
class HarnessFileTests(unittest.TestCase):
    def test_standard_files_exist(self):
        for f in HARNESS_FILES:
            self.assertTrue((ROOT / f).is_file(), f)

    def test_agents_names_both_coderskills_skills_and_the_loop_rules(self):
        t = (ROOT / "AGENTS.md").read_text("utf-8")
        self.assertIn("skills/continuous-project-loop", t)
        self.assertIn("skills/multi-project-program-management", t)
        for rule in ("Dirty worktree", "python3 tools/verify.py", "python3 tools/next_plan.py --check", "pull requests"):
            self.assertIn(rule, t)

    def test_docs_carry_the_dirty_worktree_and_record_rules(self):
        auto = (ROOT / "docs/LONG_RUNNING_AUTONOMY.md").read_text("utf-8")
        self.assertIn("Dirty worktree rule", auto)
        self.assertIn("TODO_BACKLOG.md", auto)
        cmds = (ROOT / "docs/AUTOMATION_COMMANDS.md").read_text("utf-8")
        self.assertIn("next_plan.py --check", cmds)

    def test_governance_files_are_not_stale_stubs(self):
        # the plan files must describe github-risers, not the pre-rebrand AI-only project
        for f in ("MASTER_PLAN.md", "CURRENT_PLAN.md", "TODO_BACKLOG.md"):
            self.assertNotIn("ai-growth-atlas", (ROOT / f).read_text("utf-8"), f)
        self.assertIn("categor", (ROOT / "MASTER_PLAN.md").read_text("utf-8").lower())


class PlanTests(unittest.TestCase):
    @doc_checks
    def test_current_plan_follows_the_planning_rules(self):
        self.assertEqual(next_plan.check_plan((ROOT / "CURRENT_PLAN.md").read_text("utf-8")), [])

    def test_check_flags_each_broken_rule(self):
        self.assertEqual(next_plan.check_plan(GOOD_PLAN), [])
        cases = {
            "missing section": GOOD_PLAN.replace("## Out of Scope\n\n- b\n\n", ""),
            "bad id": GOOD_PLAN.replace("PLAN-007", "plan 7"),
            "too few tasks": GOOD_PLAN.replace("- [x] two\n- [x] three\n", ""),
            "too many tasks": GOOD_PLAN.replace("- [x] three\n", "".join(f"- [ ] t{i}\n" for i in range(6))),
            "draft goal": GOOD_PLAN.replace("One clear goal.", "DRAFT: x"),
            "no verify": GOOD_PLAN.replace("python3 tools/verify.py", "run it"),
            "long goal": GOOD_PLAN.replace("One clear goal.", "a\nb\nc\nd"),
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.assertTrue(next_plan.check_plan(text), name)

    def _tmp_root(self, plan, backlog):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "CURRENT_PLAN.md").write_text(plan, "utf-8")
        (d / "TODO_BACKLOG.md").write_text(backlog, "utf-8")
        return d

    def test_open_tasks_are_never_rolled_over(self):
        d = self._tmp_root(GOOD_PLAN.replace("- [x] two", "- [ ] two"), "## Now\n\n- [ ] next thing\n")
        self.assertEqual(next_plan.main([], root=d), 0)
        self.assertIn("PLAN-007", (d / "CURRENT_PLAN.md").read_text("utf-8"))

    def test_finished_plan_rolls_to_a_draft_from_backlog_now_only(self):
        backlog = "## Now\n\n" + "".join(f"- [ ] item {i}\n" for i in range(9)) + "\n## Next\n\n- [ ] later thing\n"
        d = self._tmp_root(GOOD_PLAN, backlog)
        next_plan.main([], root=d)
        new = (d / "CURRENT_PLAN.md").read_text("utf-8")
        self.assertIn("PLAN-008", new)
        self.assertEqual(len(re.findall(r"^- \[ \] ", new, flags=re.M)), 7)   # capped at 7 tasks
        self.assertNotIn("later thing", new)                                   # only the "Now" list
        self.assertEqual(next_plan.main(["--check"], root=d), 1)               # a DRAFT must be hand-edited

    def test_empty_backlog_leaves_plan_alone(self):
        d = self._tmp_root(GOOD_PLAN, "## Now\n\n## Next\n\n- [ ] later\n")
        next_plan.main([], root=d)
        self.assertEqual((d / "CURRENT_PLAN.md").read_text("utf-8"), GOOD_PLAN)


class VerifyHardeningTests(unittest.TestCase):
    def test_verify_uses_explicit_interpreter_and_no_shell(self):
        cmds = verify.commands(ROOT)
        for c in cmds:
            self.assertEqual(c[0], sys.executable)
            self.assertIsInstance(c, list)
        src = (ROOT / "tools/verify.py").read_text("utf-8")
        self.assertNotIn("shell=True", src)
        self.assertNotRegex(src, r"""["'](?:python|pytest)\b""")
        joined = [" ".join(c[1:]) for c in cmds]
        self.assertTrue(any("compileall" in j for j in joined))
        self.assertTrue(any("unittest discover" in j for j in joined))
        self.assertTrue(any("render_readme.py --check" in j for j in joined))

    def test_no_tool_shells_out_with_a_string_command(self):
        for p in (ROOT / "tools").glob("*.py"):
            self.assertNotIn("shell=True", p.read_text("utf-8"), p.name)


class LocalDailyTests(unittest.TestCase):
    def setUp(self):
        self.sh = (ROOT / "tools/local_daily.sh").read_text("utf-8")

    def test_script_is_path_independent_and_strict(self):
        self.assertIn("set -euo pipefail", self.sh)
        self.assertRegex(self.sh, r'export PATH="[^"]*/opt/homebrew/bin[^"]*/usr/bin')
        self.assertIn('PY="$(command -v python3)"', self.sh)
        # every python call goes through "$PY": no bare `python`, `python3` or `pytest` command lines
        for line in self.sh.splitlines():
            code = line.split("#", 1)[0]
            if re.search(r"tools/\w+\.py", code):
                self.assertIn('"$PY"', code, line)

    def test_dirty_tree_and_off_main_refuse_and_order_is_update_verify_commit(self):
        self.assertIn('git status --porcelain', self.sh)
        self.assertIn("working tree not clean; refusing to run", self.sh)
        self.assertIn('!= "main"', self.sh)
        i_up = self.sh.index("tools/update_stars.py")
        i_ver = self.sh.index("tools/verify.py")
        i_commit = self.sh.index("git commit")
        self.assertLess(i_up, i_ver)
        self.assertLess(i_ver, i_commit)

    def test_workflow_verifies_before_committing(self):
        wf = (ROOT / ".github/workflows/daily-update.yml").read_text("utf-8")
        self.assertLess(wf.index("tools/verify.py"), wf.index("git commit"))


if __name__ == "__main__":
    unittest.main()
