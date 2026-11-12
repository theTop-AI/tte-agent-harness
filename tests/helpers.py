"""Shared test fixtures: an isolated HOME, a minimal harness tree, throwaway git repositories."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ISOLATED_VARS = [
    "CLAUDE_CONFIG_DIR", "CODEX_HOME", "XDG_STATE_HOME", "TTE_HARNESS_REPOSITORIES",
    "TTE_HARNESS_RUN_DIR", "TTE_HARNESS_GH", "ORCA_CLI_COMMAND", "ORCA_DEV_REPO_ROOT",
    "ORCA_TERMINAL_HANDLE", "ORCA_WORKTREE_ID", "ORCA_CLAUDE_INJECTED_CONFIG_DIR",
]

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
}

AGENT_BODY = """
# {title}

## Responsibilities

- Do the work.

## Inputs

- A brief.

## Outputs

- A result.

## Boundaries

- Stay in scope.

## Escalate when

- Something is unclear.
"""

SKILL_BODY = """
# {title}

## When to use

- When needed.

## Inputs

- Something.

## Procedure

1. Do it. See [the reference](references/detail.md).

## Outputs

- Something else.

## Validation

- It works.

## Escalate when

- It does not.
"""


class HarnessTestCase(unittest.TestCase):
    """Runs each test with HOME in a temp folder and the harness variables cleared."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self._env = dict(os.environ)
        for var in ISOLATED_VARS:
            os.environ.pop(var, None)
        os.environ["HOME"] = str(self.home)
        os.environ.update(GIT_ENV)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    # -- helpers ---------------------------------------------------------------------------

    def cli(self, root: Path, *args: str, env: dict[str, str] | None = None,
            cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        full_env = dict(os.environ)
        full_env["PYTHONPATH"] = str(root)
        full_env.update(env or {})
        return subprocess.run([sys.executable, "-m", "tte_harness", *args], cwd=cwd or root,
                              env=full_env, text=True, capture_output=True, timeout=300)

    def call(self, root: Path, *args: str) -> tuple[int, str]:
        """Run the CLI in-process (faster) from root; returns (exit code, stdout+stderr)."""
        from tte_harness import cli

        out = io.StringIO()
        prev = Path.cwd()
        os.chdir(root)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = cli.main(list(args))
        finally:
            os.chdir(prev)
        return code, out.getvalue()

    def tree(self, base: Path) -> dict[str, tuple[int, int]]:
        """Every file under base with (size, mtime_ns): to prove nothing was written."""
        out = {}
        for p in sorted(base.rglob("*")):
            if p.is_file() or p.is_symlink():
                st = p.lstat()
                out[str(p.relative_to(base))] = (st.st_size, st.st_mtime_ns)
        return out


def git(cwd: Path, *args: str) -> str:
    env = dict(os.environ)
    env.update(GIT_ENV)
    proc = subprocess.run(["git", *args], cwd=cwd, env=env, text=True, capture_output=True,
                          check=True)
    return proc.stdout.strip()


def make_fixture_harness(base: Path, commit: bool = True) -> Path:
    """A minimal but complete harness: the real code, config and templates, plus two agents, two
    skills, one workflow and one repository of its own."""
    root = base / "harness"
    root.mkdir()
    for d in ("tte_harness", "templates", "bin"):
        shutil.copytree(ROOT / d, root / d, ignore=shutil.ignore_patterns("__pycache__"))
    # Adapter READMEs link into docs/, which the fixture does not carry; only the data is needed.
    shutil.copytree(ROOT / "adapters", root / "adapters",
                    ignore=shutil.ignore_patterns("__pycache__", "*.md"))
    # Running the CLI writes __pycache__ into the checkout; the real .gitignore keeps that from
    # counting as an uncommitted change, so the fixture carries it too.
    shutil.copy(ROOT / ".gitignore", root / ".gitignore")
    (root / "config").mkdir()
    for f in ("harness.yaml", "quality-gates.yaml"):
        shutil.copy(ROOT / "config" / f, root / "config" / f)
    repo_path = base / "repos" / "demo-repo"
    (root / "config" / "repositories.example.yaml").write_text(textwrap.dedent(f"""\
        schema: 1
        repositories:
          demo-repo:
            github: example/demo-repo
            path: {repo_path}
            kind: backend
            context: [AGENTS.md]
            contract_paths: [contract/]
            roles: [builder, checker, code-reviewer]
        """))
    for name, access, skills in [("builder", "repo-write", ["build-things"]),
                                 ("checker", "read-only", ["check-things"]),
                                 ("code-reviewer", "read-only", ["check-things"])]:
        write_agent(root, name, access, skills)
    for name in ("build-things", "check-things"):
        write_skill(root, name)
    wf = root / "workflows" / "simple"
    wf.mkdir(parents=True)
    (wf / "README.md").write_text("# simple\n")
    (wf / "workflow.yaml").write_text(textwrap.dedent("""\
        schema: 1
        name: simple
        description: build then check
        stages:
          - id: build
            title: Build
            role: builder
            skills: [build-things]
            depends_on: []
          - id: check
            title: Check
            role: checker
            skills: [check-things]
            depends_on: [build]
        """))
    (root / "examples").mkdir()
    if commit:
        git(root, "init", "-q", "-b", "main")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "fixture")
    return root


def write_agent(root: Path, name: str, access: str, skills: list[str], extra: str = "",
                body: str | None = None) -> Path:
    path = root / "agents" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    front = (f"---\nname: {name}\ndescription: The {name} role, for tests.\naccess: {access}\n"
             f"skills: [{', '.join(skills)}]\n{extra}---\n")
    path.write_text(front + (body if body is not None else AGENT_BODY.format(title=name)))
    return path


def write_skill(root: Path, name: str, extra: str = "", description: str | None = None,
                body: str | None = None) -> Path:
    d = root / "skills" / name
    (d / "references").mkdir(parents=True, exist_ok=True)
    desc = description if description is not None else f"Use when tests need {name}."
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\nmetadata:\n  category: quality\n"
        f"  version: \"1.0.0\"\n{extra}---\n" + (body if body is not None
                                                else SKILL_BODY.format(title=name)))
    (d / "references" / "detail.md").write_text("# Detail\n")
    return d


def make_repo(path: Path, validate: list[dict], files: dict[str, str] | None = None) -> Path:
    """A git repository with main and a feature branch one commit ahead."""
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    (path / ".claude").mkdir()
    (path / ".claude" / "project.json").write_text(json.dumps(
        {"name": path.name, "baseBranch": "main", "validate": validate}, indent=2))
    (path / "README.md").write_text("demo\n")
    (path / "contract").mkdir()
    (path / "contract" / "openapi.json").write_text("{}\n")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "base")
    git(path, "checkout", "-q", "-b", "feature")
    for rel, text in (files or {"src/app.py": "print('hi')\n"}).items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "feature")
    return path


def write_plan(root: Path, feature_dir: Path, tasks_yaml: str) -> Path:
    spec = feature_dir / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "requirements.md").write_text("# Req\n\n## Functional requirements\n\n- FR-1 x\n")
    (spec / "api-contract.md").write_text("# Contract\n\n## Endpoints\n\nGET /things\n")
    plan = feature_dir / "plan.yaml"
    plan.write_text("schema: 1\nfeature: demo-feature\ntitle: Demo feature\nworkflow: simple\n"
                    "spec: spec\ntasks:\n" + textwrap.indent(textwrap.dedent(tasks_yaml), "  "))
    return plan


STANDARD_TASKS = """\
- id: build-it
  title: Build it
  role: builder
  repo: demo-repo
  depends_on: []
  inputs: [api-contract.md#endpoints]
  outputs: [code]
  gates: [repo-validate, clean-commit, spec-pinned, no-contract-change, no-secrets, review-pass]
  done_when: [it works]
  review_by: review-it
  status: PENDING
  blockers: []
- id: test-it
  title: Test it
  role: builder
  repo: demo-repo
  depends_on: []
  inputs: [requirements.md]
  outputs: [tests]
  gates: [repo-validate]
  done_when: [tests pass]
  status: PENDING
  blockers: []
- id: review-it
  title: Review it
  role: code-reviewer
  repo: demo-repo
  depends_on: [build-it, test-it]
  inputs: [api-contract.md]
  outputs: [verdict]
  gates: []
  done_when: [verdict recorded]
  approval: Allow the review to start?
  status: PENDING
  blockers: []
"""
