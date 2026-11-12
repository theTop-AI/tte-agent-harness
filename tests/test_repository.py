"""The real harness tree: everything it ships validates, renders and cross-references."""

import unittest

from tests.helpers import ROOT, HarnessTestCase
from tte_harness.model import load
from tte_harness.render import claude_agent, codex_agent
from tte_harness.util import parse_frontmatter
from tte_harness.validate import validate

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None

ROLES = {
    "solution-architect", "coordinator", "frontend-developer", "backend-developer",
    "frontend-qa", "backend-qa", "code-reviewer", "integration-engineer",
}
SKILLS = {
    "requirements-analysis", "solution-architecture", "api-design", "task-decomposition",
    "react-development", "python-development", "frontend-testing", "backend-testing",
    "tte-code-review", "tte-security-review", "feature-delivery", "integration-validation",
    "skill-management",
}
WORKFLOWS = {"feature-development", "bug-fixing", "code-review", "release-validation"}


class RepositoryTest(HarnessTestCase):
    def setUp(self):
        super().setUp()
        self.h = load(ROOT)

    def test_validates_without_errors(self):
        findings = validate(self.h)
        self.assertEqual([str(e) for e in findings.errors], [])

    def test_ships_every_required_role_skill_and_workflow(self):
        self.assertEqual(set(self.h.agents), ROLES)
        self.assertEqual(set(self.h.skills), SKILLS)
        self.assertEqual(set(self.h.workflows), WORKFLOWS)

    def test_every_agent_renders_for_both_providers(self):
        for agent in self.h.agents.values():
            meta, body = parse_frontmatter(claude_agent(self.h, agent, "test"))
            self.assertEqual(meta["name"], agent.name)
            self.assertTrue(body.strip())
            for skill in meta.get("skills", []):
                self.assertIn(skill, self.h.skills)
            if tomllib:
                doc = tomllib.loads(codex_agent(self.h, agent, "test"))
                self.assertEqual(doc["name"], agent.name)
                self.assertNotIn("sandbox_mode", doc, "Codex ignores sandbox_mode in agent files")
                self.assertIn(agent.body.strip().splitlines()[0], doc["developer_instructions"])

    def test_read_only_roles_cannot_edit(self):
        reviewer = self.h.agents["code-reviewer"]
        meta, _ = parse_frontmatter(claude_agent(self.h, reviewer, "test"))
        self.assertNotIn("Edit", meta["tools"])
        self.assertIn("Edit", meta["disallowedTools"])

    def test_no_skill_shadows_a_bundled_or_tte_workflows_skill(self):
        self.assertFalse(set(self.h.skills) & self.h.reserved_skills)


if __name__ == "__main__":
    unittest.main()
