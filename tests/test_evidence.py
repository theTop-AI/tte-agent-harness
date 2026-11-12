"""Evidence is recorded by commands, and each gate decides from it, not from an agent's words."""

import json
import os
import stat
import textwrap
import unittest

from tests.helpers import (
    STANDARD_TASKS,
    HarnessTestCase,
    git,
    make_fixture_harness,
    make_repo,
    write_plan,
)
from tte_harness import evidence, feature
from tte_harness.model import load
from tte_harness.util import HarnessError

PASSING = [
    {"name": "lint", "run": "test -f README.md"},
    {"name": "only-docs", "run": "exit 1", "when": "docs/*"},
]


class EvidenceTest(HarnessTestCase):
    def setUp(self):
        super().setUp()
        self.root = make_fixture_harness(self.tmp, commit=False)
        self.h = load(self.root)
        plan = feature.load_plan(write_plan(self.root, self.tmp / "feature", STANDARD_TASKS))
        feature.lock_spec(plan.spec_dir, "demo-feature", "A Person")
        self.run = self.tmp / "run"
        feature.prepare_run(self.h, plan, self.run)
        self.repo_path = self.tmp / "repos" / "demo-repo"

    def repo(self, validate=PASSING, files=None):
        return make_repo(self.repo_path, validate, files)

    def gates(self, task="build-it"):
        return {g: (r, why) for g, r, why in evidence.check_task(self.h, self.run, task)}

    def test_nothing_recorded_fails_every_mechanical_gate(self):
        rows = self.gates()
        self.assertEqual({r for r, _ in rows.values()}, {"FAIL"})

    def test_a_clean_passing_commit_passes_the_development_gates(self):
        repo = self.repo()
        rec = evidence.run_validation(self.h, self.run, "build-it", repo)
        self.assertEqual([s["name"] for s in rec["steps"]], ["lint", "only-docs"])
        self.assertTrue(rec["steps"][1]["skipped"], "a `when` that matches no changed file skips")
        self.assertEqual(rec["changed_files"], ["src/app.py"])
        rows = self.gates()
        for g in ("repo-validate", "clean-commit", "spec-pinned", "no-contract-change", "no-secrets"):
            self.assertEqual(rows[g][0], "PASS", (g, rows[g]))
        self.assertEqual(rows["review-pass"][0], "FAIL")
        log = self.run / rec["steps"][0]["log"]
        self.assertTrue(log.is_file())

    def test_a_failing_step_fails_repo_validate(self):
        repo = self.repo(validate=[{"name": "tests", "run": "echo boom; exit 3"}])
        rec = evidence.run_validation(self.h, self.run, "build-it", repo)
        self.assertEqual(rec["steps"][0]["exit_code"], 3)
        self.assertIn("boom", (self.run / rec["steps"][0]["log"]).read_text())
        self.assertEqual(self.gates()["repo-validate"], ("FAIL", "failed steps: tests"))

    def test_a_step_that_changes_the_tree_fails(self):
        repo = self.repo(validate=[{"name": "fmt", "run": "echo x >> README.md"}])
        evidence.run_validation(self.h, self.run, "build-it", repo)
        self.assertIn("changed the tree", self.gates()["repo-validate"][1])

    def test_a_dirty_tree_fails_clean_commit(self):
        repo = self.repo()
        (repo / "src" / "app.py").write_text("print('edited')\n")
        evidence.run_validation(self.h, self.run, "build-it", repo)
        self.assertEqual(self.gates()["clean-commit"][0], "FAIL")

    def test_a_contract_change_fails_unless_the_task_carries_the_approved_change(self):
        repo = self.repo(files={"contract/openapi.json": '{"paths": {}}\n'})
        evidence.run_validation(self.h, self.run, "build-it", repo)
        self.assertEqual(self.gates()["no-contract-change"],
                         ("FAIL", "contract paths changed: contract/openapi.json"))
        info = json.loads((self.run / "run.json").read_text())
        info["tasks"][0]["contract_change"] = "approved"
        (self.run / "run.json").write_text(json.dumps(info))
        self.assertEqual(self.gates()["no-contract-change"][0], "PASS")

    def test_a_credential_in_the_diff_fails_no_secrets(self):
        token = "ghp_" + "a" * 36
        repo = self.repo(files={"src/config.py": f"TOKEN = '{token}'\n"})
        rec = evidence.run_validation(self.h, self.run, "build-it", repo)
        self.assertEqual(len(rec["secret_hits"]), 1)
        self.assertIn("GitHub token", self.gates()["no-secrets"][1])

    def test_validation_without_a_committed_sequence_cannot_pass(self):
        repo = self.repo()
        git(repo, "rm", "-q", ".claude/project.json")
        git(repo, "commit", "-q", "-m", "drop config")
        evidence.run_validation(self.h, self.run, "build-it", repo)
        self.assertIn("no committed .claude/project.json", self.gates()["repo-validate"][1])

    def test_review_must_come_from_a_clean_checkout_and_match_the_validated_commit(self):
        repo = self.repo()
        evidence.run_validation(self.h, self.run, "build-it", repo)
        (repo / "scratch.txt").write_text("reviewer edit\n")
        with self.assertRaisesRegex(HarnessError, "uncommitted changes"):
            evidence.record_review(self.run, "build-it", repo, "pass", 0, None, [], "r")
        (repo / "scratch.txt").unlink()
        with self.assertRaisesRegex(HarnessError, "cannot pass"):
            evidence.record_review(self.run, "build-it", repo, "pass", 2, None, [], "r")
        evidence.record_review(self.run, "build-it", repo, "pass", 0, None,
                               ["scope-matches-task"], "reviewer-1")
        self.assertEqual(self.gates()["review-pass"][0], "PASS")
        (repo / "later.py").write_text("x = 1\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "after review")
        evidence.run_validation(self.h, self.run, "build-it", repo)
        self.assertIn("another commit", self.gates()["review-pass"][1])

    def test_pull_request_and_ci_are_read_from_github(self):
        repo = self.repo()
        evidence.run_validation(self.h, self.run, "build-it", repo)
        head = git(repo, "rev-parse", "HEAD")
        fake = self.tmp / "gh"
        fake.write_text(textwrap.dedent(f"""\
            #!/bin/sh
            if [ "$2" = "view" ]; then
              echo '{{"url": "https://github.com/example/demo-repo/pull/7", "number": 7,
                     "headRefOid": "{head}", "headRefName": "feat/x", "baseRefName": "main",
                     "state": "OPEN", "isDraft": false}}'
            else
              echo "$FAKE_CHECKS"
              exit "$FAKE_EXIT"
            fi
            """))
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["TTE_HARNESS_GH"] = str(fake)
        task = json.loads((self.run / "run.json").read_text())["tasks"][0]
        task["gates"] = ["pr-created", "ci-green"]
        info = json.loads((self.run / "run.json").read_text())
        info["tasks"][0] = task
        (self.run / "run.json").write_text(json.dumps(info))
        os.environ["FAKE_CHECKS"] = '[{"name": "ci", "state": "PENDING", "bucket": "pending"}]'
        os.environ["FAKE_EXIT"] = "8"
        evidence.record_pr(self.run, "build-it", "7")
        rows = self.gates()
        self.assertEqual(rows["pr-created"][0], "PASS")
        self.assertEqual(rows["ci-green"], ("FAIL", "checks not all green: ci=pending"))
        os.environ["FAKE_CHECKS"] = '[{"name": "ci", "state": "SUCCESS", "bucket": "pass"}]'
        os.environ["FAKE_EXIT"] = "0"
        evidence.record_pr(self.run, "build-it", "7")
        self.assertEqual(self.gates()["ci-green"][0], "PASS")

    def test_review_and_human_gates(self):
        info = json.loads((self.run / "run.json").read_text())
        info["tasks"][0]["gates"] = ["scope-matches-task", "human-merge-approval"]
        (self.run / "run.json").write_text(json.dumps(info))
        repo = self.repo()
        rows = self.gates()
        self.assertEqual(rows["human-merge-approval"][0], "HUMAN")
        self.assertEqual(rows["scope-matches-task"][0], "FAIL")
        evidence.record_review(self.run, "build-it", repo, "pass", 0, None,
                               ["scope-matches-task"], "r")
        self.assertEqual(self.gates()["scope-matches-task"][0], "PASS")

    def test_cli_exit_codes_follow_the_gates(self):
        repo = self.repo()
        code, out = self.call(self.root, "evidence", "run", "--run-dir", str(self.run),
                              "--task", "test-it", "--repo-dir", str(repo))
        self.assertEqual(code, 0, out)
        self.assertIn("PASS  lint", out)
        code, out = self.call(self.root, "evidence", "check", "--run-dir", str(self.run),
                              "--task", "test-it")
        self.assertEqual(code, 0, out)
        code, out = self.call(self.root, "evidence", "check", "--run-dir", str(self.run),
                              "--task", "build-it", "--json")
        self.assertEqual(code, 1)
        self.assertEqual({r["result"] for r in json.loads(out)}, {"FAIL"})


if __name__ == "__main__":
    unittest.main()
