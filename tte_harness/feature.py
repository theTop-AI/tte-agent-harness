"""Feature plans: the task DAG of one feature, its pinned spec, and the briefs workers receive.

A feature lives in a folder with `plan.yaml` and a `spec/` folder. `spec lock` records a digest of
every spec file once a person approved them; `plan` refuses a spec that changed since its lock, and
every brief names the digest, so each worker works against one known version.
"""

from __future__ import annotations

import datetime as _dt
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import dag
from .model import Harness, valid_name
from .util import (
    Findings,
    HarnessError,
    as_list,
    git,
    load_yaml,
    section,
    sha256_bytes,
    sha256_file,
    slug,
    headings,
    write_json,
    read_json,
)

LOCK_NAME = "spec.lock.json"
REQUIRED_TASK_KEYS = [
    "id", "title", "role", "repo", "depends_on", "inputs", "outputs", "gates", "done_when",
    "status", "blockers",
]
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
BRIEF_KEYS = frozenset({
    "feature", "feature_title", "spec_digest", "spec_commit", "spec_approved_by", "run_dir",
    "task_id", "task_title", "role", "role_description", "role_instructions", "skills", "repo",
    "repo_github", "repo_path", "repo_context", "depends_on", "inputs", "outputs", "gates",
    "done_when", "contract_rule", "review_by",
})


@dataclass
class Plan:
    path: Path
    data: dict[str, Any]

    @property
    def dir(self) -> Path:
        return self.path.parent

    @property
    def feature(self) -> str:
        return str(self.data.get("feature", ""))

    @property
    def title(self) -> str:
        return str(self.data.get("title", self.feature))

    @property
    def spec_dir(self) -> Path:
        return (self.dir / str(self.data.get("spec", "spec"))).resolve()

    @property
    def tasks(self) -> list[dict[str, Any]]:
        return [t for t in as_list(self.data.get("tasks")) if isinstance(t, dict)]

    def task(self, task_id: str) -> dict[str, Any]:
        for t in self.tasks:
            if t.get("id") == task_id:
                return t
        raise HarnessError(f"{self.path}: no task {task_id!r}")

    def deps(self) -> dict[str, list[str]]:
        return {str(t["id"]): [str(d) for d in as_list(t.get("depends_on"))]
                for t in self.tasks if "id" in t}


def load_plan(path: Path) -> Plan:
    if path.is_dir():
        path = path / "plan.yaml"
    if not path.is_file():
        raise HarnessError(f"{path}: no such plan file")
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise HarnessError(f"{path}: a plan must be a mapping")
    return Plan(path.resolve(), data)


# --- spec lock ---------------------------------------------------------------------------------

def spec_files(spec_dir: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for p in sorted(spec_dir.rglob("*")):
        if p.is_file() and not p.is_symlink() and p.name != LOCK_NAME:
            files[p.relative_to(spec_dir).as_posix()] = sha256_file(p)
    return files


def digest_of(files: dict[str, str]) -> str:
    return sha256_bytes("".join(f"{k} {v}\n" for k, v in sorted(files.items())).encode())


def lock_spec(spec_dir: Path, feature: str, approved_by: str, note: str = "") -> dict[str, Any]:
    if not spec_dir.is_dir():
        raise HarnessError(f"{spec_dir}: no such spec folder")
    if not approved_by.strip():
        raise HarnessError("--approved-by names the person who approved the spec")
    files = spec_files(spec_dir)
    if not files:
        raise HarnessError(f"{spec_dir}: the spec folder is empty")
    lock = {
        "schema": 1,
        "feature": feature,
        "files": files,
        "digest": digest_of(files),
        "approved_by": approved_by.strip(),
        "approved_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
        "note": note,
        "source": {
            "remote": git(["config", "--get", "remote.origin.url"], spec_dir),
            "commit": git(["rev-parse", "HEAD"], spec_dir),
        },
    }
    write_json(spec_dir / LOCK_NAME, lock)
    return lock


def verify_spec(spec_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Return the lock and the list of differences (empty when the spec matches its lock)."""
    lock_path = spec_dir / LOCK_NAME
    if not lock_path.is_file():
        raise HarnessError(
            f"{spec_dir}: not locked. A person approves the spec, then "
            f"`tte-harness spec lock {spec_dir} --approved-by <name>` pins it."
        )
    lock = read_json(lock_path)
    want: dict[str, str] = lock.get("files") or {}
    have = spec_files(spec_dir)
    diffs = []
    for name in sorted(set(want) | set(have)):
        if name not in have:
            diffs.append(f"removed since lock: {name}")
        elif name not in want:
            diffs.append(f"added since lock: {name}")
        elif want[name] != have[name]:
            diffs.append(f"changed since lock: {name}")
    if lock.get("digest") != digest_of(want):
        diffs.append("the lock's digest does not match its own file list (edited by hand?)")
    return lock, diffs


# --- validation -------------------------------------------------------------------------------

def validate_plan(h: Harness, plan: Plan) -> Findings:
    f = Findings()
    p = plan.path
    d = plan.data
    if d.get("schema") != 1:
        f.error(p, "schema must be 1")
    if not valid_name(plan.feature):
        f.error(p, f"feature {plan.feature!r} must be lowercase-hyphenated")
    wf = d.get("workflow")
    if wf not in h.workflows:
        f.error(p, f"workflow {wf!r} is not one of {sorted(h.workflows)}")
    if not plan.spec_dir.is_dir():
        f.error(p, f"spec folder {plan.spec_dir} does not exist")
    tasks = plan.tasks
    if not tasks:
        f.error(p, "a plan needs at least one task")
        return f
    ids: list[str] = []
    for i, t in enumerate(tasks):
        where = f"{p}#tasks[{i}]"
        missing = [k for k in REQUIRED_TASK_KEYS if k not in t]
        if missing:
            f.error(where, f"missing keys: {', '.join(missing)}")
        tid = str(t.get("id", ""))
        where = f"{p}#{tid or i}"
        if not valid_name(tid):
            f.error(where, f"id {tid!r} must be lowercase-hyphenated")
        if tid in ids:
            f.error(where, f"duplicate task id {tid!r}")
        ids.append(tid)
        for key in ("depends_on", "inputs", "outputs", "gates", "done_when", "blockers"):
            if key in t and not isinstance(t[key], list):
                f.error(where, f"{key} must be a list")
        for key in ("inputs", "outputs", "done_when"):
            if isinstance(t.get(key), list) and not t[key]:
                f.error(where, f"{key} must not be empty")
        role = t.get("role")
        if role not in h.agents:
            f.error(where, f"role {role!r} is not an agent in agents/")
        repo = t.get("repo")
        if repo not in h.repositories:
            f.error(where, f"repo {repo!r} is not in {h.repositories_file.name}")
        elif role in h.agents and role not in h.repositories[repo].roles:
            f.error(where, f"role {role!r} may not work in {repo} (repositories: roles)")
        status = t.get("status")
        if status not in h.states:
            f.error(where, f"status {status!r} is not one of {sorted(h.states)}")
        for g in as_list(t.get("gates")):
            if g not in h.gates:
                f.error(where, f"gate {g!r} is not defined in config/quality-gates.yaml")
        if "review-pass" in as_list(t.get("gates")) and not t.get("review_by"):
            f.error(where, "gate review-pass needs review_by: the id of the reviewing task")
        cc = t.get("contract_change")
        if cc is not None:
            if cc != "approved":
                f.error(where, "contract_change may only be 'approved' (the spec defines the change)")
            elif repo in h.repositories and not h.repositories[repo].contract_paths:
                f.error(where, f"contract_change on {repo}, which declares no contract_paths")
        if plan.spec_dir.is_dir():
            for ref in as_list(t.get("inputs")):
                _check_input(f, where, plan.spec_dir, str(ref))
    known = set(ids)
    for t in tasks:
        tid = str(t.get("id", ""))
        for dep in as_list(t.get("depends_on")):
            if dep not in known:
                f.error(f"{p}#{tid}", f"depends_on unknown task {dep!r}")
            if dep == tid:
                f.error(f"{p}#{tid}", "a task cannot depend on itself")
        rb = t.get("review_by")
        if rb:
            reviewer = next((x for x in tasks if x.get("id") == rb), None)
            if reviewer is None:
                f.error(f"{p}#{tid}", f"review_by unknown task {rb!r}")
            else:
                if reviewer.get("role") != "code-reviewer":
                    f.error(f"{p}#{tid}", f"review_by {rb!r} must have role code-reviewer")
                if tid not in as_list(reviewer.get("depends_on")):
                    f.error(f"{p}#{tid}", f"review task {rb!r} must depend on {tid!r}")
    cycle = dag.find_cycle(plan.deps())
    if cycle:
        f.error(p, "dependency cycle: " + " -> ".join(cycle))
    return f


def _check_input(f: Findings, where: str, spec_dir: Path, ref: str) -> None:
    name, _, anchor = ref.partition("#")
    target = spec_dir / name
    if not target.is_file():
        f.error(where, f"input {ref!r}: no file {name} in {spec_dir}")
        return
    if anchor and anchor not in {slug(hd) for hd in headings(target.read_text(encoding="utf-8"))}:
        f.error(where, f"input {ref!r}: {name} has no heading with anchor #{anchor}")


# --- briefs -----------------------------------------------------------------------------------

def render_template(template: str, values: dict[str, str]) -> str:
    missing = sorted({m.group(1) for m in PLACEHOLDER_RE.finditer(template)} - set(values))
    if missing:
        raise HarnessError(f"template placeholders without a value: {', '.join(missing)}")
    return PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], template)


def input_text(spec_dir: Path, ref: str) -> str:
    name, _, anchor = ref.partition("#")
    text = (spec_dir / name).read_text(encoding="utf-8")
    if not anchor:
        return text.strip() + "\n"
    for hd in headings(text):
        if slug(hd) == anchor:
            return section(text, hd) or ""
    raise HarnessError(f"{name}: no heading #{anchor}")


def bullet(items: list[Any], empty: str = "- none") -> str:
    return "\n".join(f"- {x}" for x in items) if items else empty


def brief_values(h: Harness, plan: Plan, task: dict[str, Any], lock: dict[str, Any],
                 run_dir: Path) -> dict[str, str]:
    agent = h.agents[task["role"]]
    repo = h.repositories[task["repo"]]
    gates = [f"`{g}` ({h.gates[g]['kind']}): {' '.join(str(h.gates[g]['description']).split())}"
             for g in task.get("gates", [])]
    inputs = []
    for ref in task.get("inputs", []):
        inputs.append(f"#### `{ref}`\n\n{input_text(plan.spec_dir, ref).rstrip()}\n")
    if task.get("contract_change") == "approved":
        contract = ("This task carries the approved contract change from the spec. Implement it "
                    "exactly as specified; any other change to "
                    + ", ".join(f"`{p}`" for p in repo.contract_paths)
                    + " needs a new approval from the coordinator.")
    elif repo.contract_paths:
        contract = ("Do not change " + ", ".join(f"`{p}`" for p in repo.contract_paths)
                    + ". If the work seems to need it, stop and ask the coordinator "
                    "(`orca orchestration ask`).")
    else:
        contract = "This repository declares no contract paths."
    return {
        "feature": plan.feature,
        "feature_title": plan.title,
        "spec_digest": str(lock.get("digest")),
        "spec_commit": str((lock.get("source") or {}).get("commit") or "not in git"),
        "spec_approved_by": str(lock.get("approved_by")),
        "run_dir": str(run_dir),
        "task_id": str(task["id"]),
        "task_title": str(task["title"]),
        "role": agent.name,
        "role_description": " ".join(agent.description.split()),
        "role_instructions": agent.body.strip(),
        "skills": bullet([f"`{s}`" for s in agent.skills]),
        "repo": repo.name,
        "repo_github": repo.github,
        "repo_path": str(repo.path),
        "repo_context": bullet([f"`{c}`" for c in as_list(repo.data.get("context"))]),
        "depends_on": bullet([f"`{d}`" for d in task.get("depends_on", [])]),
        "inputs": "\n".join(inputs),
        "outputs": bullet(task.get("outputs", [])),
        "gates": bullet(gates),
        "done_when": bullet(task.get("done_when", [])),
        "contract_rule": contract,
        "review_by": f"`{task['review_by']}`" if task.get("review_by") else "none",
    }


def prepare_run(h: Harness, plan: Plan, run_dir: Path) -> dict[str, Any]:
    """Validate the plan, check its spec lock, and write the run folder: a read-only copy of the
    pinned spec, the resolved plan, and one brief per task. Returns the run summary."""
    findings = validate_plan(h, plan)
    if findings.errors:
        raise HarnessError("plan is invalid:\n" + "\n".join(str(e) for e in findings.errors))
    lock, diffs = verify_spec(plan.spec_dir)
    if diffs:
        raise HarnessError("the spec changed since it was approved and locked:\n  "
                           + "\n  ".join(diffs))
    order = dag.waves(plan.deps())
    template = (h.root / "templates" / "task-brief.md").read_text(encoding="utf-8")
    run_dir.mkdir(parents=True, exist_ok=True)
    spec_copy = run_dir / "spec"
    if spec_copy.exists():
        _make_writable(spec_copy)
        shutil.rmtree(spec_copy)
    shutil.copytree(plan.spec_dir, spec_copy)
    _make_read_only(spec_copy)
    briefs = run_dir / "briefs"
    briefs.mkdir(exist_ok=True)
    for t in plan.tasks:
        text = render_template(template, brief_values(h, plan, t, lock, run_dir))
        (briefs / f"{t['id']}.md").write_text(text, encoding="utf-8")
    summary = {
        "schema": 1,
        "feature": plan.feature,
        "title": plan.title,
        "plan": str(plan.path),
        "spec_digest": lock["digest"],
        "waves": order,
        "tasks": plan.tasks,
    }
    write_json(run_dir / "run.json", summary)
    return summary


def _make_read_only(root: Path) -> None:
    for p in [root, *root.rglob("*")]:
        mode = p.stat().st_mode
        p.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _make_writable(root: Path) -> None:
    for p in [root, *root.rglob("*")]:
        p.chmod(p.stat().st_mode | stat.S_IWUSR)


def load_run(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run.json"
    if not path.is_file():
        raise HarnessError(f"{run_dir}: not a run folder (no run.json); create it with "
                           "`tte-harness plan <plan.yaml> --run-dir <dir>`")
    return read_json(path)
