"""Evidence: what makes a task complete, recorded by commands rather than by an agent's report.

    evidence run     run the repository's own validation sequence on the committed worktree
    evidence review  record an independent reviewer's verdict on one commit
    evidence pr      record the pull request and the checks GitHub reports on its head
    evidence check   decide every gate of a task from what was recorded

Everything lands in <run-dir>/evidence/<task>/ as JSON plus logs.
"""

from __future__ import annotations

import datetime as _dt
import fnmatch
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .feature import load_run
from .model import Harness
from .secrets import scan_diff
from .util import HarnessError, as_list, git, read_json, run, write_json

DEFAULT_STEP_TIMEOUT = 1800


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _task(run_info: dict[str, Any], task_id: str) -> dict[str, Any]:
    for t in run_info.get("tasks", []):
        if t.get("id") == task_id:
            return t
    raise HarnessError(f"task {task_id!r} is not in this run ({run_info.get('feature')})")


def evidence_dir(run_dir: Path, task_id: str) -> Path:
    return run_dir / "evidence" / task_id


def _repo_root(repo_dir: Path) -> Path:
    top = git(["rev-parse", "--show-toplevel"], repo_dir)
    if not top:
        raise HarnessError(f"{repo_dir}: not inside a git worktree")
    return Path(top)


def _project_config(root: Path) -> dict[str, Any] | None:
    path = root / ".claude" / "project.json"
    if not path.is_file():
        return None
    try:
        return read_json(path)
    except json.JSONDecodeError as exc:
        raise HarnessError(f"{path}: invalid JSON: {exc}") from exc


def _base_ref(root: Path, project: dict[str, Any] | None, base: str | None) -> str:
    if base:
        return base
    branch = (project or {}).get("baseBranch") or "main"
    remote = f"origin/{branch}"
    return remote if git(["rev-parse", "--verify", "--quiet", remote], root) else branch


def _matches(when: Any, changed: list[str]) -> bool:
    patterns = [str(p) for p in as_list(when)]
    if not patterns:
        return True
    return any(fnmatch.fnmatchcase(c, p) for p in patterns for c in changed)


def _touches(path: str, contract_paths: list[str]) -> bool:
    for cp in contract_paths:
        if cp.endswith("/") and path.startswith(cp):
            return True
        if path == cp:
            return True
    return False


def run_validation(h: Harness, run_dir: Path, task_id: str, repo_dir: Path,
                   base: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    run_info = load_run(run_dir)
    task = _task(run_info, task_id)
    root = _repo_root(repo_dir)
    repo = h.repositories.get(task["repo"])
    contract_paths = repo.contract_paths if repo else []
    project = _project_config(root)
    base_ref = _base_ref(root, project, base)
    head = git(["rev-parse", "HEAD"], root)
    status = git(["status", "--porcelain", "--untracked-files=normal"], root) or ""
    merge_base = git(["merge-base", base_ref, "HEAD"], root)
    if not merge_base:
        raise HarnessError(f"{root}: no merge-base with {base_ref}; fetch it or pass --base")
    changed = [c for c in (git(["diff", "--name-only", f"{merge_base}..HEAD"], root) or "")
               .splitlines() if c]
    diff = git(["diff", f"{merge_base}..HEAD"], root) or ""
    steps_cfg = as_list((project or {}).get("validate"))
    out_dir = evidence_dir(run_dir, task_id)
    logs = out_dir / "logs"
    record: dict[str, Any] = {
        "schema": 1,
        "task": task_id,
        "repo": task["repo"],
        "worktree": str(root),
        "head": head,
        "base": base_ref,
        "merge_base": merge_base,
        "dirty": bool(status.strip()),
        "spec_digest": run_info.get("spec_digest"),
        "validation_source": ".claude/project.json" if project is not None else None,
        "changed_files": changed,
        "contract_changed": [c for c in changed if _touches(c, contract_paths)],
        "secret_hits": [str(hit) for hit in scan_diff(diff)],
        "steps": [],
        "recorded_at": _now(),
    }
    if dry_run:
        record["steps"] = [{"name": s.get("name"), "run": s.get("run"),
                            "would_run": _matches(s.get("when"), changed)} for s in steps_cfg]
        return record
    if out_dir.exists():
        shutil.rmtree(out_dir / "logs", ignore_errors=True)
    logs.mkdir(parents=True, exist_ok=True)
    for i, step in enumerate(steps_cfg, 1):
        name = str(step.get("name", f"step-{i}"))
        cmd = str(step.get("run", ""))
        entry: dict[str, Any] = {"name": name, "run": cmd}
        if not _matches(step.get("when"), changed):
            entry.update(skipped=True, reason="no changed file matches `when`")
            record["steps"].append(entry)
            continue
        log = logs / f"{i:02d}-{name}.log"
        started = time.monotonic()
        timeout = float(step.get("timeout") or DEFAULT_STEP_TIMEOUT)
        with log.open("w", encoding="utf-8") as fh:
            try:
                proc = subprocess.run(["bash", "-c", cmd], cwd=root, stdout=fh,
                                      stderr=subprocess.STDOUT, timeout=timeout, check=False,
                                      start_new_session=True)
                code = proc.returncode
            except subprocess.TimeoutExpired:
                code = 124
                fh.write(f"\n[tte-harness] timed out after {timeout:.0f}s\n")
        entry.update(exit_code=code, seconds=round(time.monotonic() - started, 1),
                     log=str(log.relative_to(run_dir)))
        record["steps"].append(entry)
    after = git(["status", "--porcelain", "--untracked-files=normal"], root) or ""
    record["tree_changed_by_steps"] = after.strip() != status.strip()
    write_json(out_dir / "validation.json", record)
    return record


def record_review(run_dir: Path, task_id: str, repo_dir: Path, verdict: str, critical: int,
                  findings: Path | None, attested: list[str], reviewer: str) -> dict[str, Any]:
    if verdict not in {"pass", "fail"}:
        raise HarnessError("--verdict is pass or fail")
    if critical < 0:
        raise HarnessError("--critical counts unresolved critical findings (0 or more)")
    if verdict == "pass" and critical:
        raise HarnessError("a review with unresolved critical findings cannot pass")
    run_info = load_run(run_dir)
    _task(run_info, task_id)
    root = _repo_root(repo_dir)
    status = git(["status", "--porcelain", "--untracked-files=normal"], root) or ""
    if status.strip():
        raise HarnessError(
            f"{root} has uncommitted changes. A reviewer reads and never edits; record the verdict "
            "from a clean checkout of the commit under review.")
    out_dir = evidence_dir(run_dir, task_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    findings_copy = None
    if findings:
        if not findings.is_file():
            raise HarnessError(f"{findings}: no such findings file")
        findings_copy = out_dir / "review-findings.md"
        shutil.copyfile(findings, findings_copy)
    record = {
        "schema": 1,
        "task": task_id,
        "verdict": verdict,
        "critical": critical,
        "head": git(["rev-parse", "HEAD"], root),
        "attested_gates": sorted(set(attested)),
        "reviewer": reviewer or os.environ.get("ORCA_DISPATCH_ID") or "unnamed",
        "findings": str(findings_copy.relative_to(run_dir)) if findings_copy else None,
        "recorded_at": _now(),
    }
    write_json(out_dir / "review.json", record)
    return record


def _gh() -> str:
    return os.environ.get("TTE_HARNESS_GH", "gh")


def record_pr(run_dir: Path, task_id: str, pr: str) -> dict[str, Any]:
    run_info = load_run(run_dir)
    _task(run_info, task_id)
    view = run([_gh(), "pr", "view", pr, "--json",
                "url,number,headRefOid,headRefName,baseRefName,state,isDraft"], timeout=60)
    if view.returncode != 0:
        raise HarnessError(f"gh pr view {pr} failed: {view.stderr.strip() or view.stdout.strip()}")
    info = json.loads(view.stdout)
    checks_proc = run([_gh(), "pr", "checks", pr, "--json", "name,state,bucket,link"], timeout=60)
    # gh exits 8 while checks are pending and 1 when one failed; the JSON is still printed.
    try:
        checks = json.loads(checks_proc.stdout or "[]")
    except json.JSONDecodeError:
        checks = []
    buckets = [str(c.get("bucket", "")).lower() for c in checks]
    ci_green = bool(checks) and all(b in {"pass", "skipping"} for b in buckets)
    record = {
        "schema": 1,
        "task": task_id,
        "url": info.get("url"),
        "number": info.get("number"),
        "head": info.get("headRefOid"),
        "head_branch": info.get("headRefName"),
        "base_branch": info.get("baseRefName"),
        "state": info.get("state"),
        "draft": info.get("isDraft"),
        "checks": checks,
        "ci_green": ci_green,
        "recorded_at": _now(),
    }
    write_json(evidence_dir(run_dir, task_id) / "pr.json", record)
    return record


def _load(path: Path) -> dict[str, Any] | None:
    return read_json(path) if path.is_file() else None


def check_task(h: Harness, run_dir: Path, task_id: str) -> list[tuple[str, str, str]]:
    """Return (gate, result, reason) rows; result is PASS, FAIL or HUMAN."""
    run_info = load_run(run_dir)
    task = _task(run_info, task_id)
    ev = evidence_dir(run_dir, task_id)
    val = _load(ev / "validation.json")
    rev = _load(ev / "review.json")
    pr = _load(ev / "pr.json")
    rows: list[tuple[str, str, str]] = []

    def need_val() -> str | None:
        return None if val else "no validation recorded (tte-harness evidence run)"

    for gate in as_list(task.get("gates")):
        spec = h.gates.get(gate)
        if spec is None:
            rows.append((gate, "FAIL", "gate not defined in config/quality-gates.yaml"))
            continue
        kind = spec.get("kind")
        reason: str | None = None
        if kind == "human":
            rows.append((gate, "HUMAN", "a person resolves the Orca decision gate; never an agent"))
            continue
        if kind == "review":
            if not rev:
                reason = "no review recorded (tte-harness evidence review)"
            elif rev.get("verdict") != "pass":
                reason = "the review did not pass"
            elif gate not in rev.get("attested_gates", []):
                reason = "the reviewer did not attest this gate (--attest)"
            rows.append((gate, "FAIL" if reason else "PASS", reason or "attested by the reviewer"))
            continue
        if gate == "repo-validate":
            reason = need_val()
            if not reason:
                ran = [s for s in val["steps"] if not s.get("skipped")]
                failed = [s["name"] for s in ran if s.get("exit_code") != 0]
                if val.get("validation_source") is None:
                    reason = "the repository has no committed .claude/project.json validate list"
                elif not ran:
                    reason = "no validation step ran"
                elif failed:
                    reason = "failed steps: " + ", ".join(failed)
                elif val.get("tree_changed_by_steps"):
                    reason = "a validation step changed the tree (generated or formatted files)"
        elif gate == "clean-commit":
            reason = need_val() or ("the tree had uncommitted changes" if val["dirty"] else None)
        elif gate == "spec-pinned":
            reason = need_val() or (None if val.get("spec_digest") == run_info.get("spec_digest")
                                    else "evidence was recorded against another spec digest")
        elif gate == "no-contract-change":
            reason = need_val()
            if not reason and val["contract_changed"] and task.get("contract_change") != "approved":
                reason = "contract paths changed: " + ", ".join(val["contract_changed"])
        elif gate == "no-secrets":
            reason = need_val() or ("; ".join(val["secret_hits"]) if val["secret_hits"] else None)
        elif gate == "review-pass":
            if not rev:
                reason = "no review recorded"
            elif rev.get("verdict") != "pass" or rev.get("critical"):
                reason = f"review verdict {rev.get('verdict')} with {rev.get('critical')} critical"
            elif val and rev.get("head") != val.get("head"):
                reason = "the review was of another commit than the validated one"
        elif gate == "pr-created":
            if not pr:
                reason = "no pull request recorded (tte-harness evidence pr)"
            elif val and pr.get("head") != val.get("head"):
                reason = "the pull request head is not the validated commit; validate it again"
        elif gate == "ci-green":
            if not pr:
                reason = "no pull request recorded"
            elif not pr.get("ci_green"):
                states = ", ".join(f"{c.get('name')}={c.get('bucket')}" for c in pr["checks"])
                reason = "checks not all green: " + (states or "none reported")
        else:
            reason = "no evidence rule for this gate"
        rows.append((gate, "FAIL" if reason else "PASS", reason or "recorded"))
    return rows
