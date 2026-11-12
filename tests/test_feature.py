"""Feature plans: DAG validation, spec lock and tamper detection, run preparation and briefs."""

import os
import re
import unittest

from tests.helpers import STANDARD_TASKS, HarnessTestCase, make_fixture_harness, write_plan
from tte_harness import feature
from tte_harness.model import load
from tte_harness.util import HarnessError


class FeatureTest(HarnessTestCase):
    def setUp(self):
        super().setUp()
        self.root = make_fixture_harness(self.tmp, commit=False)
        self.h = load(self.root)
        self.fdir = self.tmp / "feature"

    def plan(self, tasks=STANDARD_TASKS):
        return feature.load_plan(write_plan(self.root, self.fdir, tasks))

    def errors(self, plan):
        return [str(e) for e in feature.validate_plan(self.h, plan).errors]

    def test_standard_plan_is_valid_and_has_parallel_waves(self):
        plan = self.plan()
        self.assertEqual(self.errors(plan), [])
        from tte_harness import dag
        self.assertEqual(dag.waves(plan.deps()), [["build-it", "test-it"], ["review-it"]])

    def test_cycle_is_rejected(self):
        tasks = STANDARD_TASKS.replace("  depends_on: []\n  inputs: [api-contract.md#endpoints]",
                                       "  depends_on: [review-it]\n  inputs: [api-contract.md#endpoints]")
        self.assertTrue(any("dependency cycle" in e for e in self.errors(self.plan(tasks))))

    def test_unknown_role_repo_gate_and_dependency(self):
        tasks = (STANDARD_TASKS.replace("role: builder\n  repo: demo-repo\n  depends_on: []\n"
                                        "  inputs: [requirements.md]",
                                        "role: wizard\n  repo: nowhere\n  depends_on: [ghost]\n"
                                        "  inputs: [requirements.md]")
                 .replace("gates: [repo-validate]\n", "gates: [vibes]\n"))
        errs = self.errors(self.plan(tasks))
        for frag in ("role 'wizard' is not an agent", "repo 'nowhere'", "gate 'vibes'",
                     "depends_on unknown task 'ghost'"):
            self.assertTrue(any(frag in e for e in errs), (frag, errs))

    def test_role_must_be_allowed_in_the_repository(self):
        cfg = self.root / "config" / "repositories.example.yaml"
        cfg.write_text(cfg.read_text().replace("roles: [builder, checker, code-reviewer]",
                                               "roles: [checker, code-reviewer]"))
        self.h = load(self.root)
        self.assertTrue(any("may not work in demo-repo" in e for e in self.errors(self.plan())))

    def test_review_pass_needs_a_reviewer_task_that_depends_on_the_work(self):
        tasks = STANDARD_TASKS.replace("depends_on: [build-it, test-it]", "depends_on: [test-it]")
        self.assertTrue(any("must depend on 'build-it'" in e for e in self.errors(self.plan(tasks))))
        tasks = STANDARD_TASKS.replace("  review_by: review-it\n", "")
        self.assertTrue(any("needs review_by" in e for e in self.errors(self.plan(tasks))))

    def test_inputs_must_exist_down_to_the_heading(self):
        tasks = STANDARD_TASKS.replace("api-contract.md#endpoints", "api-contract.md#nope")
        self.assertTrue(any("no heading with anchor #nope" in e
                            for e in self.errors(self.plan(tasks))))

    def test_missing_required_task_fields(self):
        tasks = STANDARD_TASKS.replace("  done_when: [tests pass]\n", "")
        self.assertTrue(any("missing keys: done_when" in e for e in self.errors(self.plan(tasks))))

    def test_spec_lock_detects_every_kind_of_change(self):
        plan = self.plan()
        lock = feature.lock_spec(plan.spec_dir, "demo-feature", "A Person")
        self.assertTrue(lock["digest"].startswith("sha256:"))
        self.assertEqual(feature.verify_spec(plan.spec_dir)[1], [])
        (plan.spec_dir / "api-contract.md").write_text("# Contract\n\n## Endpoints\n\nPOST /x\n")
        (plan.spec_dir / "extra.md").write_text("new\n")
        (plan.spec_dir / "requirements.md").unlink()
        diffs = feature.verify_spec(plan.spec_dir)[1]
        self.assertIn("changed since lock: api-contract.md", diffs)
        self.assertIn("added since lock: extra.md", diffs)
        self.assertIn("removed since lock: requirements.md", diffs)

    def test_lock_needs_an_approver(self):
        plan = self.plan()
        with self.assertRaises(HarnessError):
            feature.lock_spec(plan.spec_dir, "demo-feature", "  ")

    def test_prepare_run_refuses_an_unlocked_or_changed_spec(self):
        plan = self.plan()
        with self.assertRaisesRegex(HarnessError, "not locked"):
            feature.prepare_run(self.h, plan, self.tmp / "run")
        feature.lock_spec(plan.spec_dir, "demo-feature", "A Person")
        (plan.spec_dir / "requirements.md").write_text("changed\n")
        with self.assertRaisesRegex(HarnessError, "changed since it was approved"):
            feature.prepare_run(self.h, plan, self.tmp / "run")

    def test_prepare_run_writes_self_contained_briefs_and_a_read_only_spec(self):
        plan = self.plan()
        lock = feature.lock_spec(plan.spec_dir, "demo-feature", "A Person")
        run = self.tmp / "run"
        summary = feature.prepare_run(self.h, plan, run)
        self.assertEqual(summary["waves"], [["build-it", "test-it"], ["review-it"]])
        brief = (run / "briefs" / "build-it.md").read_text()
        self.assertNotRegex(brief, r"\{\{\s*[a-z_]+\s*\}\}")
        self.assertIn(lock["digest"], brief)
        self.assertIn("GET /things", brief, "the brief quotes the pinned spec section")
        self.assertIn("## Responsibilities", brief, "the brief carries the role instructions")
        self.assertIn("`contract/`", brief, "the brief states the contract rule")
        self.assertIn(f"--run-dir {run}", brief)
        spec_copy = run / "spec" / "api-contract.md"
        self.assertTrue(spec_copy.is_file())
        self.assertFalse(os.access(spec_copy, os.W_OK) and os.geteuid() != 0)
        # Preparing again replaces the read-only copy cleanly.
        feature.prepare_run(self.h, plan, run)

    def test_template_placeholders_must_all_have_values(self):
        with self.assertRaisesRegex(HarnessError, "without a value: nope"):
            feature.render_template("{{ task_id }} {{nope}}", {"task_id": "x"})
        self.assertEqual(feature.render_template("a {{ x }} b", {"x": "1"}), "a 1 b")
        used = set(re.findall(r"\{\{\s*([a-z_]+)\s*\}\}",
                              (self.root / "templates" / "task-brief.md").read_text()))
        self.assertLessEqual(used, set(feature.BRIEF_KEYS))


if __name__ == "__main__":
    unittest.main()
