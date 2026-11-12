"""The Orca bridge against a fake orca CLI that answers like Orca 1.4.256 (--json --full)."""

import json
import os
import stat
import textwrap
import unittest
from unittest import mock

from tests.helpers import STANDARD_TASKS, HarnessTestCase, make_fixture_harness, write_plan
from tte_harness import feature, orca
from tte_harness.model import load
from tte_harness.util import HarnessError

FAKE_ORCA = r'''#!/usr/bin/env python3
"""Answers like Orca's CLI with --json --full, and logs every call."""
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_ORCA_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
def flag(name):
    return args[args.index(name) + 1] if name in args else None
n = sum(1 for _ in open(os.environ["FAKE_ORCA_LOG"]))
if args[:2] == ["orchestration", "run-create"]:
    out = {"run": {"id": "run_1", "objective": flag("--objective")}}
elif args[:2] == ["orchestration", "task-create"]:
    if os.environ.get("FAKE_ORCA_FAIL_TASK") == str(n):
        print(json.dumps({"ok": False, "error": {"code": "boom", "message": "refused"}}))
        sys.exit(1)
    out = {"task": {"id": "task_%d" % n, "status": "pending", "deps": flag("--deps")}}
elif args[:2] == ["orchestration", "gate-create"]:
    out = {"gate": {"id": "gate_%d" % n, "task_id": flag("--task"), "status": "pending"}}
else:
    print(json.dumps({"ok": False, "error": {"code": "unknown", "message": " ".join(args)}}))
    sys.exit(1)
print(json.dumps({"id": "x", "ok": True, "result": out}))
'''


class OrcaTest(HarnessTestCase):
    def setUp(self):
        super().setUp()
        self.root = make_fixture_harness(self.tmp, commit=False)
        self.h = load(self.root)
        plan = feature.load_plan(write_plan(self.root, self.tmp / "feature", STANDARD_TASKS))
        feature.lock_spec(plan.spec_dir, "demo-feature", "A Person")
        self.run = self.tmp / "run"
        feature.prepare_run(self.h, plan, self.run)
        self.fake = self.tmp / "orca"
        self.fake.write_text(FAKE_ORCA)
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IXUSR)
        self.log = self.tmp / "orca.log"
        os.environ["FAKE_ORCA_LOG"] = str(self.log)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_commands_follow_dependency_order_and_carry_briefs(self):
        steps = orca.build_commands(self.run)
        kinds = [(s["kind"], s.get("id")) for s in steps]
        self.assertEqual(kinds, [("run", None), ("task", "build-it"), ("task", "test-it"),
                                 ("task", "review-it"), ("gate", "review-it")])
        self.assertIn(str(self.run / "briefs" / "build-it.md"), steps[1]["args"])
        script = orca.render_script(steps)
        self.assertIn("--deps '[\"<orca-id:build-it>\", \"<orca-id:test-it>\"]'", script)
        self.assertIn("--json --full", script)

    def test_create_builds_the_dag_with_orca_ids(self):
        mapping = orca.create(self.run, str(self.fake))
        self.assertEqual(mapping["run_id"], "run_1")
        self.assertTrue(mapping["complete"])
        calls = self.calls()
        review = next(c for c in calls if "review-it: Review it" in c)
        deps = json.loads(review[review.index("--deps") + 1])
        self.assertEqual(deps, [mapping["tasks"]["build-it"], mapping["tasks"]["test-it"]])
        self.assertEqual(review[review.index("--run") + 1], "run_1")
        gate = calls[-1]
        self.assertEqual(gate[:2], ["orchestration", "gate-create"])
        self.assertEqual(gate[gate.index("--task") + 1], mapping["tasks"]["review-it"])
        self.assertIn("--full", gate)
        with self.assertRaisesRegex(HarnessError, "already exists in Orca"):
            orca.create(self.run, str(self.fake))

    def test_a_failure_part_way_leaves_an_exact_record(self):
        os.environ["FAKE_ORCA_FAIL_TASK"] = "3"
        with self.assertRaisesRegex(HarnessError, "boom: refused"):
            orca.create(self.run, str(self.fake))
        mapping = json.loads((self.run / orca.MAP_NAME).read_text())
        self.assertFalse(mapping["complete"])
        self.assertEqual(list(mapping["tasks"]), ["build-it"])
        with self.assertRaisesRegex(HarnessError, "stopped part way"):
            orca.create(self.run, str(self.fake))

    def test_lifecycle_maps_orca_statuses_and_evidence(self):
        (self.run / orca.MAP_NAME).write_text(json.dumps({"run_id": "r", "complete": True, "tasks": {
            "build-it": "t1", "test-it": "t2", "review-it": "t3"}}))

        def states(s1, s2, s3, ev, r1=None):
            tasks = [{"id": "t1", "status": s1, "result": r1}, {"id": "t2", "status": s2},
                     {"id": "t3", "status": s3}]
            return orca.lifecycle(self.run, tasks, ev)

        none = {}
        self.assertEqual(states("pending", "ready", "pending", none),
                         {"build-it": "PENDING", "test-it": "READY", "review-it": "PENDING"})
        self.assertEqual(states("dispatched", "failed", "blocked", none, None)["build-it"], "RUNNING")
        self.assertEqual(states("dispatched", "failed", "blocked", none)["test-it"], "FAILED")
        self.assertEqual(states("dispatched", "failed", "blocked", none)["review-it"],
                         "NEEDS_APPROVAL", "a blocked task with an approval gate needs a person")
        self.assertEqual(states("failed", "ready", "pending", none, "cancelled by user")["build-it"],
                         "CANCELLED")
        self.assertEqual(states("completed", "ready", "pending", {"build-it": (False, False)})
                         ["build-it"], "VALIDATING", "done is not complete without evidence")
        self.assertEqual(states("completed", "ready", "ready", {"build-it": (True, False)})
                         ["build-it"], "REVIEW")
        self.assertEqual(states("completed", "completed", "completed",
                                {"build-it": (True, True)})["build-it"], "COMPLETED")

    def test_cli_resolution_follows_the_official_skill(self):
        os.environ["ORCA_CLI_COMMAND"] = "/opt/orca/bin/orca-wsl"
        self.assertEqual(orca.resolve_cli()[0], "/opt/orca/bin/orca-wsl")
        del os.environ["ORCA_CLI_COMMAND"]
        bindir = self.tmp / "bin"
        bindir.mkdir()
        os.environ["PATH"] = str(bindir)
        with mock.patch.object(orca.sys, "platform", "linux"):
            self.assertIsNone(orca.resolve_cli()[0], "nothing on PATH")
            (bindir / "orca").symlink_to(self.fake)
            self.assertIsNone(orca.resolve_cli()[0], "bare orca outside an Orca terminal is refused")
            os.environ["ORCA_TERMINAL_HANDLE"] = "term_1"
            self.assertEqual(orca.resolve_cli()[0], str(bindir / "orca"))
            (bindir / "orca-ide").symlink_to(self.fake)
            self.assertEqual(orca.resolve_cli()[0], str(bindir / "orca-ide"))
        with mock.patch.object(orca.sys, "platform", "darwin"):
            self.assertEqual(orca.resolve_cli()[0], str(bindir / "orca"))

    def test_review_gates_do_not_hold_a_task_in_validating(self):
        """Regression: a review-kind gate on an implementation task must not make REVIEW
        unreachable (it used to count as a development gate)."""
        from tests.helpers import make_repo
        from tte_harness import evidence
        info = json.loads((self.run / "run.json").read_text())
        info["tasks"][0]["gates"] = ["repo-validate", "scope-matches-task"]
        (self.run / "run.json").write_text(json.dumps(info))
        repo = make_repo(self.tmp / "repos" / "demo-repo", [{"name": "ok", "run": "true"}])
        evidence.run_validation(self.h, self.run, "build-it", repo)
        (self.run / orca.MAP_NAME).write_text(json.dumps({"run_id": "r", "complete": True, "tasks": {
            "build-it": "t1", "test-it": "t2", "review-it": "t3"}}))
        saved = self.tmp / "tasks.json"
        saved.write_text(json.dumps({"ok": True, "result": {"tasks": [
            {"id": "t1", "status": "completed"}, {"id": "t2", "status": "ready"},
            {"id": "t3", "status": "pending"}]}}))
        code, out = self.call(self.root, "status", "--run-dir", str(self.run), "--orca-json",
                              str(saved))
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"REVIEW\s+build-it")
        evidence.record_review(self.run, "build-it", repo, "pass", 0, None,
                               ["scope-matches-task"], "r")
        saved.write_text(saved.read_text().replace('"t3", "status": "pending"',
                                                   '"t3", "status": "completed"'))
        code, out = self.call(self.root, "status", "--run-dir", str(self.run), "--orca-json",
                              str(saved))
        self.assertRegex(out, r"COMPLETED\s+build-it")

    def test_status_command_reads_a_saved_task_list(self):
        (self.run / orca.MAP_NAME).write_text(json.dumps({"run_id": "r", "complete": True, "tasks": {
            "build-it": "t1", "test-it": "t2", "review-it": "t3"}}))
        saved = self.tmp / "tasks.json"
        saved.write_text(json.dumps({"ok": True, "result": {"tasks": [
            {"id": "t1", "status": "dispatched"}, {"id": "t2", "status": "completed"},
            {"id": "t3", "status": "pending"}]}}))
        code, out = self.call(self.root, "status", "--run-dir", str(self.run), "--orca-json",
                              str(saved))
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"RUNNING\s+build-it")
        self.assertRegex(out, r"VALIDATING\s+test-it")
        self.assertRegex(out, r"PENDING\s+review-it")


if __name__ == "__main__":
    unittest.main()
