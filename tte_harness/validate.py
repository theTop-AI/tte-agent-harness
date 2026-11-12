"""`tte-harness validate`: every structural rule of the harness source tree in one pass."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from . import dag
from .feature import (
    BRIEF_KEYS,
    PLACEHOLDER_RE,
    load_plan,
    prepare_run,
    validate_plan,
    verify_spec,
)
from .model import (
    AGENT_SECTIONS,
    GATE_KINDS,
    GATE_STAGES,
    SKILL_CATEGORIES,
    SKILL_SECTIONS,
    TEMPLATES,
    Harness,
    valid_name,
)
from .render import claude_agent, codex_agent
from .secrets import scan_files
from .util import Findings, HarnessError, as_list, headings, iter_files, parse_frontmatter

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None  # type: ignore[assignment]

AGENT_KEYS = {"name", "description", "access", "skills", "model", "codex"}
# The portable Agent Skills fields (agentskills.io); both Claude Code and Codex read them.
SKILL_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
MODELS = {"inherit", "sonnet", "opus", "haiku", "fable"}
EFFORTS = {"minimal", "low", "medium", "high", "xhigh"}
ORCA_STATUSES = {"pending", "ready", "dispatched", "completed", "failed", "blocked"}
REQUIRED_STATES = {"PENDING", "READY", "RUNNING", "VALIDATING", "REVIEW", "COMPLETED", "BLOCKED",
                   "FAILED", "CANCELLED", "NEEDS_APPROVAL"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
SKILL_MAX_LINES = 500


def _missing_sections(body: str, required: list[str]) -> list[str]:
    have = {h.strip().lower() for h in headings(body)}
    return [s for s in required if s.lower() not in have]


def check_agents(h: Harness, f: Findings) -> None:
    for name, agent in h.agents.items():
        p = agent.path
        meta_name = agent.meta.get("name")
        if meta_name != name:
            f.error(p, f"frontmatter name {meta_name!r} must equal the file name {name!r}")
        if not valid_name(name):
            f.error(p, "agent names are lowercase letters, digits and hyphens, at most 64 chars")
        if name in h.reserved_agents:
            f.error(p, f"{name!r} is reserved (config/harness.yaml reserved.agents)")
        for key in sorted(set(agent.meta) - AGENT_KEYS):
            f.error(p, f"unknown frontmatter key {key!r}; allowed: {', '.join(sorted(AGENT_KEYS))}")
        if not agent.description:
            f.error(p, "description is required: it is how a session decides to delegate")
        elif len(agent.description) > 1024:
            f.error(p, "description is longer than 1024 characters")
        if agent.access not in h.access_levels:
            f.error(p, f"access {agent.access!r} is not one of {sorted(h.access_levels)}")
        if not agent.skills:
            f.error(p, "skills must list at least one harness skill")
        for s in agent.skills:
            if s not in h.skills:
                f.error(p, f"skill {s!r} does not exist in skills/")
        model = agent.meta.get("model")
        if model is not None and model not in MODELS and not str(model).startswith("claude-"):
            f.error(p, f"model {model!r} is not inherit, an alias or a claude-* model id")
        codex = agent.meta.get("codex") or {}
        if not isinstance(codex, dict) or set(codex) - {"reasoning_effort"}:
            f.error(p, "codex may only carry reasoning_effort")
        elif codex.get("reasoning_effort") and codex["reasoning_effort"] not in EFFORTS:
            f.error(p, f"codex.reasoning_effort must be one of {sorted(EFFORTS)}")
        for sec in _missing_sections(agent.body, AGENT_SECTIONS):
            f.error(p, f"missing section '## {sec}'")
        if agent.access in h.access_levels and not f.errors_for(p):
            _check_renders(h, agent, f)


def _check_renders(h: Harness, agent, f: Findings) -> None:
    try:
        meta, _ = parse_frontmatter(claude_agent(h, agent, "validate"))
        if meta.get("name") != agent.name:
            f.error(agent.path, "rendered Claude Code agent lost its name")
    except HarnessError as exc:
        f.error(agent.path, f"rendered Claude Code agent is invalid: {exc}")
    if tomllib is not None:
        try:
            doc = tomllib.loads(codex_agent(h, agent, "validate"))
            for key in ("name", "description", "developer_instructions"):
                if not doc.get(key):
                    f.error(agent.path, f"rendered Codex agent has no {key}")
        except tomllib.TOMLDecodeError as exc:
            f.error(agent.path, f"rendered Codex agent is not valid TOML: {exc}")


def check_skills(h: Harness, f: Findings) -> None:
    used = {s for a in h.agents.values() for s in a.skills}
    for name, skill in h.skills.items():
        p = skill.path / "SKILL.md"
        if skill.meta.get("name") != name:
            f.error(p, f"frontmatter name {skill.meta.get('name')!r} must equal the folder {name!r}")
        if not valid_name(name):
            f.error(p, "skill names are lowercase letters, digits and hyphens, at most 64 chars")
        if name in h.reserved_skills:
            f.error(p, f"{name!r} is reserved: another tool installs a skill with this name in the "
                       "same folder (config/harness.yaml reserved.skills)")
        for key in sorted(set(skill.meta) - SKILL_KEYS):
            f.error(p, f"frontmatter key {key!r} is not a portable Agent Skills field; "
                       f"allowed: {', '.join(sorted(SKILL_KEYS))}")
        desc = skill.description
        if not desc:
            f.error(p, "description is required")
        else:
            if len(desc) > 1024:
                f.error(p, "description is longer than 1024 characters")
            if "use when" not in desc.lower():
                f.error(p, "description must say when to use the skill ('Use when ...')")
        meta = skill.meta.get("metadata") or {}
        if not isinstance(meta, dict):
            f.error(p, "metadata must be a mapping")
        else:
            if meta.get("category") not in SKILL_CATEGORIES:
                f.error(p, f"metadata.category must be one of {sorted(SKILL_CATEGORIES)}")
            if not SEMVER_RE.match(str(meta.get("version", ""))):
                f.error(p, "metadata.version must be MAJOR.MINOR.PATCH")
            for k, v in meta.items():
                if not isinstance(v, str):
                    f.error(p, f"metadata.{k} must be a string (Agent Skills metadata is str->str)")
        for sec in _missing_sections(skill.body, SKILL_SECTIONS):
            f.error(p, f"missing section '## {sec}'")
        lines = skill.body.count("\n") + 1
        if lines > SKILL_MAX_LINES:
            f.error(p, f"SKILL.md body is {lines} lines; keep it under {SKILL_MAX_LINES} and move "
                       "detail to references/")
        linked = set()
        for target in LINK_RE.findall(skill.body):
            if "://" in target or target.startswith("#"):
                continue
            rel = target.split("#")[0]
            linked.add((skill.path / rel).resolve())
        for extra in sorted(skill.path.rglob("*")):
            if extra.is_file() and extra.name != "SKILL.md" and extra.resolve() not in linked:
                f.warn(extra, "not linked from SKILL.md, so an agent will never open it")
        if name not in used:
            f.warn(p, "no agent lists this skill")


def check_workflows(h: Harness, f: Findings) -> None:
    for name, wf in h.workflows.items():
        p = wf.path
        d = wf.data
        if d.get("schema") != 1:
            f.error(p, "schema must be 1")
        if d.get("name") != name:
            f.error(p, f"name {d.get('name')!r} must equal the folder {name!r}")
        if not str(d.get("description", "")).strip():
            f.error(p, "description is required")
        if not (wf.path.parent / "README.md").is_file():
            f.error(wf.path.parent, "a workflow needs a README.md that a person can follow")
        stages = wf.stages
        if not stages:
            f.error(p, "a workflow needs stages")
            continue
        ids: list[str] = []
        for st in stages:
            sid = str(st.get("id", ""))
            where = f"{p}#{sid}"
            if not valid_name(sid):
                f.error(where, f"stage id {sid!r} must be lowercase-hyphenated")
            if sid in ids:
                f.error(where, "duplicate stage id")
            ids.append(sid)
            for key in ("title", "role"):
                if not st.get(key):
                    f.error(where, f"{key} is required")
            role = st.get("role")
            if role and role not in h.agents:
                f.error(where, f"role {role!r} is not an agent")
            for s in as_list(st.get("skills")):
                if s not in h.skills:
                    f.error(where, f"skill {s!r} does not exist")
                elif role in h.agents and s not in h.agents[role].skills:
                    f.warn(where, f"skill {s!r} is not in {role}'s skills")
            for g in as_list(st.get("gates")):
                if g not in h.gates:
                    f.error(where, f"gate {g!r} is not defined")
        deps = {str(st.get("id")): [str(x) for x in as_list(st.get("depends_on"))]
                for st in stages}
        for sid, ds in deps.items():
            for dep in ds:
                if dep not in deps:
                    f.error(f"{p}#{sid}", f"depends_on unknown stage {dep!r}")
        cycle = dag.find_cycle(deps)
        if cycle:
            f.error(p, "dependency cycle: " + " -> ".join(cycle))


def check_config(h: Harness, f: Findings) -> None:
    cfg = h.root / "config" / "harness.yaml"
    if h.config.get("schema") != 1:
        f.error(cfg, "schema must be 1")
    missing = REQUIRED_STATES - set(h.states)
    if missing:
        f.error(cfg, f"states is missing {sorted(missing)}")
    for state, spec in h.states.items():
        if (spec or {}).get("orca_status") not in ORCA_STATUSES:
            f.error(cfg, f"state {state}: orca_status must be one of {sorted(ORCA_STATUSES)}")
    for level, spec in h.access_levels.items():
        if not as_list((spec or {}).get("tools")):
            f.error(cfg, f"access {level}: tools is empty")
        if (spec or {}).get("codex_sandbox") not in {"read-only", "workspace-write"}:
            f.error(cfg, f"access {level}: codex_sandbox must be read-only or workspace-write")
    gates = h.root / "config" / "quality-gates.yaml"
    for name, g in h.gates.items():
        if not valid_name(name):
            f.error(gates, f"gate {name!r} must be lowercase-hyphenated")
        if g.get("kind") not in GATE_KINDS:
            f.error(gates, f"gate {name}: kind must be one of {sorted(GATE_KINDS)}")
        if g.get("stage") not in GATE_STAGES:
            f.error(gates, f"gate {name}: stage must be one of {sorted(GATE_STAGES)}")
        if g.get("stage") == "development" and g.get("kind") != "evidence":
            f.error(gates, f"gate {name}: a development-stage gate must be kind evidence, so a "
                           "worker can pass it alone; a reviewer's or a person's gate belongs "
                           "to the review or delivery stage")
        if not str(g.get("description", "")).strip():
            f.error(gates, f"gate {name}: description is required")
    check_repositories(h, f)


def check_repositories(h: Harness, f: Findings) -> None:
    p = h.repositories_file
    if not h.repositories:
        f.error(p, "no repositories")
    for name, repo in h.repositories.items():
        where = f"{p}#{name}"
        if not valid_name(name):
            f.error(where, "repository keys are lowercase-hyphenated")
        if not re.match(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", repo.github):
            f.error(where, "github must be owner/name")
        if not str(repo.data.get("path", "")).startswith(("/", "~")):
            f.error(where, "path must be absolute (or start with ~)")
        if not repo.data.get("kind"):
            f.error(where, "kind is required")
        if not repo.roles:
            f.error(where, "roles must list the agents allowed to work here")
        for r in repo.roles:
            if r not in h.agents:
                f.error(where, f"role {r!r} is not an agent")
        if not isinstance(repo.data.get("contract_paths", []), list):
            f.error(where, "contract_paths must be a list")


def check_templates(h: Harness, f: Findings) -> None:
    tdir = h.root / "templates"
    for t in TEMPLATES:
        if not (tdir / t).is_file():
            f.error(tdir / t, "required template is missing")
    brief = tdir / "task-brief.md"
    if brief.is_file():
        used = {m.group(1) for m in PLACEHOLDER_RE.finditer(brief.read_text(encoding="utf-8"))}
        for unknown in sorted(used - BRIEF_KEYS):
            f.error(brief, f"placeholder {{{{{unknown}}}}} has no value; known: "
                           f"{', '.join(sorted(BRIEF_KEYS))}")
        for key in ("task_id", "spec_digest", "role_instructions", "inputs", "gates", "run_dir"):
            if key not in used:
                f.error(brief, f"the brief must carry {{{{{key}}}}}")


def check_examples(h: Harness, f: Findings) -> None:
    for plan_path in sorted((h.root / "examples").glob("*/plan.yaml")):
        try:
            plan = load_plan(plan_path)
        except HarnessError as exc:
            f.error(plan_path, str(exc))
            continue
        res = validate_plan(h, plan)
        f.extend(res)
        if res.errors:
            continue
        try:
            _, diffs = verify_spec(plan.spec_dir)
        except HarnessError as exc:
            f.error(plan_path, str(exc))
            continue
        for d in diffs:
            f.error(plan.spec_dir, d)
        if not diffs:
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    prepare_run(h, plan, Path(tmp) / "run")
                except HarnessError as exc:
                    f.error(plan_path, f"cannot prepare a run: {exc}")


def check_links(h: Harness, f: Findings) -> None:
    for md in iter_files(h.root):
        if md.suffix != ".md" or ".git" in md.parts or "examples" in md.relative_to(h.root).parts[:1]:
            continue
        text = md.read_text(encoding="utf-8")
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        for target in LINK_RE.findall(text):
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            rel = target.split("#")[0]
            if rel and not (md.parent / rel).exists():
                f.error(md, f"broken link: {target}")


def check_secrets(h: Harness, f: Findings) -> None:
    files = [p for p in iter_files(h.root) if ".git" not in p.relative_to(h.root).parts]
    for hit in scan_files(files, h.root):
        f.error(hit.where, f"line {hit.line}: looks like a {hit.kind}; never commit credentials")


def validate(h: Harness) -> Findings:
    f = Findings()
    for path, msg in h.load_errors:
        f.error(path, msg)
    check_config(h, f)
    check_skills(h, f)
    check_agents(h, f)
    check_workflows(h, f)
    check_templates(h, f)
    check_examples(h, f)
    check_links(h, f)
    check_secrets(h, f)
    return f
