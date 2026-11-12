"""Each validation rule fires on the defect it exists for, in a fixture harness."""

import textwrap
import unittest

from tests.helpers import (
    HarnessTestCase,
    make_fixture_harness,
    write_agent,
    write_skill,
)
from tte_harness.model import load
from tte_harness.validate import validate


class ValidationRulesTest(HarnessTestCase):
    def setUp(self):
        super().setUp()
        self.root = make_fixture_harness(self.tmp, commit=False)

    def errors(self):
        return [str(e) for e in validate(load(self.root)).errors]

    def assertError(self, fragment):
        errs = self.errors()
        self.assertTrue(any(fragment in e for e in errs), f"no error with {fragment!r} in {errs}")

    def test_fixture_is_valid(self):
        self.assertEqual(self.errors(), [])

    # agents
    def test_agent_missing_section(self):
        write_agent(self.root, "builder", "repo-write", ["build-things"],
                    body="# builder\n\n## Responsibilities\n\n- x\n")
        self.assertError("missing section '## Inputs'")

    def test_agent_unknown_skill(self):
        write_agent(self.root, "builder", "repo-write", ["no-such-skill"])
        self.assertError("skill 'no-such-skill' does not exist")

    def test_agent_unknown_access(self):
        write_agent(self.root, "builder", "root", ["build-things"])
        self.assertError("access 'root' is not one of")

    def test_agent_name_must_match_file(self):
        path = write_agent(self.root, "builder", "repo-write", ["build-things"])
        path.write_text(path.read_text().replace("name: builder", "name: other"))
        self.assertError("must equal the file name")

    def test_agent_unknown_key(self):
        write_agent(self.root, "builder", "repo-write", ["build-things"],
                    extra="permissionMode: bypassPermissions\n")
        self.assertError("unknown frontmatter key 'permissionMode'")

    def test_reserved_agent_name(self):
        write_agent(self.root, "general-purpose", "read-only", ["check-things"])
        self.assertError("'general-purpose' is reserved")

    # skills
    def test_skill_without_skill_md(self):
        (self.root / "skills" / "empty").mkdir()
        self.assertError("skill directory has no SKILL.md")

    def test_skill_name_must_match_folder(self):
        d = write_skill(self.root, "build-things")
        md = d / "SKILL.md"
        md.write_text(md.read_text().replace("name: build-things", "name: build"))
        self.assertError("must equal the folder")

    def test_skill_reserved_name(self):
        write_skill(self.root, "code-review")
        self.assertError("'code-review' is reserved")

    def test_skill_must_say_when_to_use(self):
        write_skill(self.root, "build-things", description="Builds things.")
        self.assertError("must say when to use")

    def test_skill_non_portable_key(self):
        write_skill(self.root, "build-things", extra="context: fork\n")
        self.assertError("'context' is not a portable Agent Skills field")

    def test_skill_broken_reference_link(self):
        d = write_skill(self.root, "build-things")
        (d / "references" / "detail.md").unlink()
        self.assertError("broken link: references/detail.md")

    def test_skill_bad_metadata(self):
        d = write_skill(self.root, "build-things")
        md = d / "SKILL.md"
        md.write_text(md.read_text().replace('version: "1.0.0"', "version: 1"))
        self.assertError("metadata.version must be MAJOR.MINOR.PATCH")

    # workflows
    def test_workflow_cycle(self):
        wf = self.root / "workflows" / "simple" / "workflow.yaml"
        wf.write_text(wf.read_text().replace("depends_on: []", "depends_on: [check]"))
        self.assertError("dependency cycle")

    def test_workflow_unknown_role_and_gate(self):
        wf = self.root / "workflows" / "loose"
        wf.mkdir()
        (wf / "README.md").write_text("# loose\n")
        (wf / "workflow.yaml").write_text(textwrap.dedent("""\
            schema: 1
            name: loose
            description: x
            stages:
              - id: one
                title: One
                role: wizard
                gates: [vibes]
                depends_on: [zero]
            """))
        self.assertError("role 'wizard' is not an agent")
        self.assertError("gate 'vibes' is not defined")
        self.assertError("depends_on unknown stage 'zero'")

    def test_workflow_needs_readme(self):
        (self.root / "workflows" / "simple" / "README.md").unlink()
        self.assertError("needs a README.md")

    # repositories and config
    def test_repository_unknown_role(self):
        cfg = self.root / "config" / "repositories.example.yaml"
        cfg.write_text(cfg.read_text().replace("roles: [builder", "roles: [ghost, builder"))
        self.assertError("role 'ghost' is not an agent")

    def test_repository_relative_path(self):
        cfg = self.root / "config" / "repositories.example.yaml"
        text = cfg.read_text()
        start = text.index("path: ") + len("path: ")
        end = text.index("\n", start)
        cfg.write_text(text[:start] + "relative/path" + text[end:])
        self.assertError("path must be absolute")

    def test_state_mapping_uses_real_orca_statuses(self):
        cfg = self.root / "config" / "harness.yaml"
        cfg.write_text(cfg.read_text().replace("orca_status: dispatched", "orca_status: running"))
        self.assertError("orca_status must be one of")

    def test_development_gates_must_be_mechanical(self):
        cfg = self.root / "config" / "quality-gates.yaml"
        cfg.write_text(cfg.read_text().replace("  scope-matches-task:\n    stage: review",
                                               "  scope-matches-task:\n    stage: development"))
        self.assertError("gate scope-matches-task: a development-stage gate must be kind evidence")

    # secrets
    def test_credential_in_a_file_is_an_error(self):
        key = "AKIA" + "ABCDEFGHIJKLMNOP"
        (self.root / "skills" / "build-things" / "references" / "detail.md").write_text(
            f"# Detail\n\naws key {key}\n")
        self.assertError("looks like a AWS access key id")


if __name__ == "__main__":
    unittest.main()
