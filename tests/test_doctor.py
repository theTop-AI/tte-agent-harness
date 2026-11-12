"""doctor reports every failure with a fix, and never skips one silently."""

import json
import os
import unittest

from tests.helpers import HarnessTestCase, make_fixture_harness


class DoctorTest(HarnessTestCase):
    def setUp(self):
        super().setUp()
        self.root = make_fixture_harness(self.tmp)

    def doctor(self):
        code, out = self.call(self.root, "doctor", "--json", "--offline")
        return code, {c["name"]: c for c in json.loads(out)}

    def test_missing_tools_and_install_fail_with_a_fix(self):
        os.environ["PATH"] = "/usr/bin:/bin"
        code, checks = self.doctor()
        self.assertEqual(code, 1)
        self.assertEqual(checks["claude code"]["status"], "FAIL")
        self.assertIn("install Claude Code", checks["claude code"]["fix"])
        self.assertEqual(checks["codex"]["status"], "WARN", "Codex is optional")
        self.assertEqual(checks["harness installed"]["status"], "FAIL")
        self.assertIn("install.sh", checks["harness installed"]["fix"])
        for c in checks.values():
            if c["status"] == "FAIL":
                self.assertTrue(c["fix"] or c["name"].startswith("repo "), c)

    def test_after_install_skills_are_discoverable(self):
        self.assertEqual(self.call(self.root, "install", "--providers", "claude,codex")[0], 0)
        _, checks = self.doctor()
        self.assertEqual(checks["harness installed"]["status"], "OK", checks["harness installed"])
        self.assertEqual(checks["skills discoverable"]["status"], "OK")
        agent = self.home / ".claude" / "agents" / "builder.md"
        agent.write_text("edited\n")
        _, checks = self.doctor()
        self.assertEqual(checks["harness installed"]["status"], "FAIL")
        self.assertIn("1 edited", checks["harness installed"]["detail"])

    def test_managed_orca_account_is_flagged(self):
        os.environ["ORCA_CLAUDE_INJECTED_CONFIG_DIR"] = "/somewhere/account"
        _, checks = self.doctor()
        self.assertEqual(checks["claude config dir"]["status"], "WARN")

    def test_repositories_are_checked_for_checkout_worktrees_and_validation(self):
        _, checks = self.doctor()
        self.assertEqual(checks["repo demo-repo"]["status"], "WARN")
        self.assertIn("git clone", checks["repo demo-repo"]["fix"])


if __name__ == "__main__":
    unittest.main()
