"""Installation in an isolated HOME: placement, dry run, idempotency, conflicts, uninstall."""

import json
import os
import stat
import unittest

from tests.helpers import HarnessTestCase, git, make_fixture_harness

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


class InstallTest(HarnessTestCase):
    def setUp(self):
        super().setUp()
        self.root = make_fixture_harness(self.tmp)
        self.claude = self.home / ".claude"
        self.codex = self.home / ".codex"
        self.agents_skills = self.home / ".agents" / "skills"
        self.manifest = self.home / ".local" / "state" / "tte-agent-harness" / "install-manifest.json"

    def install(self, *extra):
        return self.call(self.root, "install", "--providers", "claude,codex", *extra)

    def test_dry_run_writes_nothing(self):
        before = self.tree(self.home)
        code, out = self.install("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("dry run: nothing written", out)
        self.assertIn("create", out)
        self.assertEqual(self.tree(self.home), before)

    def test_installs_skills_agents_and_cli_where_each_tool_reads_them(self):
        code, out = self.install()
        self.assertEqual(code, 0, out)
        self.assertTrue((self.claude / "skills" / "build-things" / "SKILL.md").is_file())
        self.assertTrue((self.claude / "skills" / "build-things" / "references" / "detail.md").is_file())
        self.assertTrue((self.agents_skills / "check-things" / "SKILL.md").is_file())
        claude_agent = (self.claude / "agents" / "checker.md").read_text()
        self.assertIn("name: checker", claude_agent)
        self.assertIn("disallowedTools: Edit, Write, NotebookEdit", claude_agent)
        codex_agent = self.codex / "agents" / "builder.toml"
        self.assertTrue(codex_agent.is_file())
        if tomllib:
            doc = tomllib.loads(codex_agent.read_text())
            self.assertEqual(doc["name"], "builder")
            self.assertIn("developer_instructions", doc)
        cli = self.home / ".local" / "bin" / "tte-harness"
        self.assertTrue(cli.stat().st_mode & stat.S_IXUSR)
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(manifest["source"]["commit"], git(self.root, "rev-parse", "HEAD"))
        self.assertIn(str(self.claude / "agents" / "checker.md"), manifest["files"])

    def test_second_install_changes_nothing(self):
        self.assertEqual(self.install()[0], 0)
        before = self.tree(self.home)
        code, out = self.install()
        self.assertEqual(code, 0, out)
        self.assertIn("installed: ", out)
        for op in ("create", "update", "conflict", "force", "remove"):
            self.assertNotIn(f"\n{op} ", "\n" + out)
        after = self.tree(self.home)
        changed = {k for k in after if before.get(k) != after[k]}
        self.assertEqual(changed, {".local/state/tte-agent-harness/install-manifest.json"})

    def test_unrelated_configuration_is_untouched_by_install_and_uninstall(self):
        (self.claude / "skills" / "my-own-skill").mkdir(parents=True)
        (self.claude / "skills" / "my-own-skill" / "SKILL.md").write_text("mine\n")
        (self.claude / "agents").mkdir(parents=True)
        (self.claude / "agents" / "mine.md").write_text("mine\n")
        (self.claude / "settings.json").write_text('{"model": "opus"}\n')
        self.codex.mkdir()
        (self.codex / "config.toml").write_text('model = "x"\n')
        theirs = {p: p.read_bytes() for p in [
            self.claude / "skills" / "my-own-skill" / "SKILL.md", self.claude / "agents" / "mine.md",
            self.claude / "settings.json", self.codex / "config.toml"]}
        self.assertEqual(self.install()[0], 0)
        self.assertEqual(self.call(self.root, "uninstall")[0], 0)
        for path, data in theirs.items():
            self.assertEqual(path.read_bytes(), data, path)
        self.assertFalse((self.claude / "skills" / "build-things").exists())
        self.assertFalse((self.codex / "agents" / "builder.toml").exists())
        self.assertFalse(self.manifest.exists())

    def test_a_foreign_skill_with_the_same_name_is_a_conflict_not_an_overwrite(self):
        theirs = self.claude / "skills" / "build-things"
        theirs.mkdir(parents=True)
        (theirs / "SKILL.md").write_text("someone else's skill\n")
        code, out = self.install()
        self.assertEqual(code, 3, out)
        self.assertIn("conflict", out)
        self.assertEqual((theirs / "SKILL.md").read_text(), "someone else's skill\n")
        self.assertFalse((theirs / "references").exists(), "never mix files into a foreign skill")
        code, out = self.install("--force")
        self.assertEqual(code, 0, out)
        self.assertIn("name: build-things", (theirs / "SKILL.md").read_text())
        backups = list((self.home / ".local" / "state" / "tte-agent-harness" / "backups").rglob("SKILL.md"))
        self.assertEqual([b.read_text() for b in backups], ["someone else's skill\n"])

    def test_a_locally_edited_file_is_kept_on_reinstall_and_uninstall(self):
        self.assertEqual(self.install()[0], 0)
        agent = self.claude / "agents" / "builder.md"
        agent.write_text(agent.read_text() + "\nmy local note\n")
        code, out = self.install()
        self.assertEqual(code, 3)
        self.assertIn("edited since the harness installed it", out)
        self.assertIn("my local note", agent.read_text())
        code, out = self.call(self.root, "uninstall")
        self.assertEqual(code, 0, out)
        self.assertIn("keep", out)
        self.assertTrue(agent.exists())

    def test_permissions_are_added_and_removed_without_touching_the_rest(self):
        self.claude.mkdir()
        settings = self.claude / "settings.json"
        settings.write_text(json.dumps({"model": "opus", "permissions": {
            "deny": ["Bash(rm -rf /)"], "allow": ["Bash(ls)"]}}))
        code, out = self.install("--with-permissions")
        self.assertEqual(code, 0, out)
        data = json.loads(settings.read_text())
        self.assertEqual(data["model"], "opus")
        self.assertEqual(data["permissions"]["allow"], ["Bash(ls)"])
        self.assertIn("Bash(rm -rf /)", data["permissions"]["deny"])
        self.assertIn("Bash(gh pr merge *)", data["permissions"]["deny"])
        self.assertIn("Bash(aws *)", data["permissions"]["ask"])
        code, out = self.install("--with-permissions")
        self.assertEqual(json.loads(settings.read_text()), data, "rules are not added twice")
        self.assertEqual(self.call(self.root, "uninstall")[0], 0)
        self.assertEqual(json.loads(settings.read_text()), {
            "model": "opus", "permissions": {"deny": ["Bash(rm -rf /)"], "allow": ["Bash(ls)"]}})

    def test_a_dirty_checkout_or_wrong_ref_is_refused(self):
        (self.root / "README.md").write_text("uncommitted\n")
        code, out = self.install()
        self.assertEqual(code, 2)
        self.assertIn("uncommitted changes", out)
        self.assertEqual(self.install("--allow-dirty")[0], 0)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "readme")
        git(self.root, "tag", "v9.9.9", "HEAD~1")
        code, out = self.install("--ref", "v9.9.9")
        self.assertEqual(code, 2)
        self.assertIn("not v9.9.9", out)

    def test_an_invalid_source_installs_nothing(self):
        (self.root / "skills" / "build-things" / "SKILL.md").write_text("no frontmatter\n")
        git(self.root, "commit", "-qam", "break")
        before = self.tree(self.home)
        code, out = self.install()
        self.assertEqual(code, 2, out)
        self.assertIn("does not validate", out)
        self.assertEqual(self.tree(self.home), before)

    def test_providers_are_detected_from_existing_config(self):
        os.environ["PATH"] = "/usr/bin:/bin"  # no claude or codex binary
        code, out = self.call(self.root, "install", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("found neither Claude Code nor Codex", out)
        self.claude.mkdir()
        code, out = self.call(self.root, "install", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("provider   claude", out)
        self.assertNotIn("provider   codex", out)

    def test_shell_entry_point_runs_end_to_end(self):
        proc = self.cli(self.root, "install", "--providers", "claude", "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("dry run", proc.stdout)


if __name__ == "__main__":
    unittest.main()
