"""Load the harness source tree: config, agents, skills, workflows, gates, repositories."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .util import (
    NAME_RE,
    HarnessError,
    as_list,
    load_yaml,
    parse_frontmatter,
)

AGENT_SECTIONS = ["Responsibilities", "Inputs", "Outputs", "Boundaries", "Escalate when"]
SKILL_SECTIONS = ["When to use", "Inputs", "Procedure", "Outputs", "Validation", "Escalate when"]
SKILL_CATEGORIES = {"planning", "development", "quality", "delivery"}
GATE_KINDS = {"evidence", "review", "human"}
GATE_STAGES = {"development", "review", "delivery"}
TEMPLATES = [
    "requirements.md",
    "architecture.md",
    "api-contract.md",
    "test-plan.md",
    "task-brief.md",
    "delivery-report.md",
    "plan.yaml",
]


@dataclass
class Agent:
    name: str
    path: Path
    meta: dict[str, Any]
    body: str

    @property
    def description(self) -> str:
        return str(self.meta.get("description", "")).strip()

    @property
    def access(self) -> str:
        return str(self.meta.get("access", ""))

    @property
    def skills(self) -> list[str]:
        return [str(s) for s in as_list(self.meta.get("skills"))]


@dataclass
class Skill:
    name: str
    path: Path  # the skill directory
    meta: dict[str, Any]
    body: str

    @property
    def description(self) -> str:
        return str(self.meta.get("description", "")).strip()


@dataclass
class Workflow:
    name: str
    path: Path  # workflow.yaml
    data: dict[str, Any]

    @property
    def stages(self) -> list[dict[str, Any]]:
        return [s for s in as_list(self.data.get("stages")) if isinstance(s, dict)]


@dataclass
class Repository:
    name: str
    data: dict[str, Any]

    @property
    def path(self) -> Path:
        return Path(str(self.data.get("path", ""))).expanduser()

    @property
    def roles(self) -> list[str]:
        return [str(r) for r in as_list(self.data.get("roles"))]

    @property
    def contract_paths(self) -> list[str]:
        return [str(p) for p in as_list(self.data.get("contract_paths"))]

    @property
    def github(self) -> str:
        return str(self.data.get("github", ""))


@dataclass
class Harness:
    root: Path
    config: dict[str, Any]
    gates: dict[str, dict[str, Any]]
    repositories: dict[str, Repository]
    repositories_file: Path
    agents: dict[str, Agent] = field(default_factory=dict)
    skills: dict[str, Skill] = field(default_factory=dict)
    workflows: dict[str, Workflow] = field(default_factory=dict)
    load_errors: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def access_levels(self) -> dict[str, dict[str, Any]]:
        return dict(self.config.get("access") or {})

    @property
    def states(self) -> dict[str, dict[str, Any]]:
        return dict(self.config.get("states") or {})

    @property
    def reserved_skills(self) -> set[str]:
        return {str(n) for n in as_list((self.config.get("reserved") or {}).get("skills"))}

    @property
    def reserved_agents(self) -> set[str]:
        return {str(n) for n in as_list((self.config.get("reserved") or {}).get("agents"))}


def find_root(start: Path | None = None) -> Path:
    """The harness checkout: the directory holding config/harness.yaml, from start upwards, else
    the directory this package was loaded from."""
    candidates = []
    if start is not None:
        candidates.extend([start, *start.resolve().parents])
    candidates.append(Path(__file__).resolve().parent.parent)
    for c in candidates:
        if (c / "config" / "harness.yaml").is_file() and (c / "tte_harness").is_dir():
            return c.resolve()
    raise HarnessError("cannot find the harness checkout (no config/harness.yaml above here)")


def repositories_file(root: Path) -> Path:
    """TTE_HARNESS_REPOSITORIES (a simulation or test), else config/repositories.yaml (this
    host), else the committed example."""
    override = os.environ.get("TTE_HARNESS_REPOSITORIES")
    if override:
        return Path(override).expanduser().resolve()
    local = root / "config" / "repositories.yaml"
    return local if local.is_file() else root / "config" / "repositories.example.yaml"


def load(root: Path) -> Harness:
    config = load_yaml(root / "config" / "harness.yaml") or {}
    gates_doc = load_yaml(root / "config" / "quality-gates.yaml") or {}
    repo_file = repositories_file(root)
    repos_doc = load_yaml(repo_file) or {}
    repos = {
        str(name): Repository(str(name), data or {})
        for name, data in (repos_doc.get("repositories") or {}).items()
    }
    h = Harness(
        root=root,
        config=config,
        gates={str(k): (v or {}) for k, v in (gates_doc.get("gates") or {}).items()},
        repositories=repos,
        repositories_file=repo_file,
    )
    for path in sorted((root / "agents").glob("*.md")):
        try:
            meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except HarnessError as exc:
            h.load_errors.append((path, str(exc)))
            continue
        h.agents[path.stem] = Agent(path.stem, path, meta, body)
    for skill_dir in sorted(p for p in (root / "skills").iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            h.load_errors.append((skill_dir, "skill directory has no SKILL.md"))
            continue
        try:
            meta, body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        except HarnessError as exc:
            h.load_errors.append((skill_md, str(exc)))
            continue
        h.skills[skill_dir.name] = Skill(skill_dir.name, skill_dir, meta, body)
    for wf_dir in sorted(p for p in (root / "workflows").iterdir() if p.is_dir()):
        wf = wf_dir / "workflow.yaml"
        if not wf.is_file():
            h.load_errors.append((wf_dir, "workflow directory has no workflow.yaml"))
            continue
        try:
            data = load_yaml(wf) or {}
        except HarnessError as exc:
            h.load_errors.append((wf, str(exc)))
            continue
        h.workflows[wf_dir.name] = Workflow(wf_dir.name, wf, data)
    return h


def valid_name(name: str) -> bool:
    return bool(NAME_RE.match(name)) and len(name) <= 64
