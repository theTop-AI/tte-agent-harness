"""The bridge to Orca: resolve the CLI the official skills would use, turn a prepared run into an
Orca Run with one Task per plan task (dependencies and decision gates included), and read task
states back into the harness's lifecycle names.

Orca keeps the Run, the Tasks, the workers and the mail; the harness only creates the DAG from an
approved plan and reports. Starting workers is the coordinator agent's job, through the
`orchestration` skill (`orca orchestration worker-start --task <id> ...`).

Receipt shapes were read from the Orca 1.4.256 CLI (handlers/orchestration/*.js): with
`--json --full` a receipt is the raw response, `{"ok": true, "result": {"run"|"task"|"gate": {...}}}`.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

from . import dag
from .feature import load_run
from .util import HarnessError, as_list, read_json, run, write_json

MAP_NAME = "orca-map.json"


def resolve_cli() -> tuple[str | None, str]:
    """Pick the Orca executable the way the official orca-cli/orchestration skills do.

    Returns (executable or None, explanation)."""
    env = os.environ.get("ORCA_CLI_COMMAND")
    if env:
        return env, "ORCA_CLI_COMMAND"
    if os.environ.get("ORCA_DEV_REPO_ROOT") and shutil.which("orca-dev"):
        return "orca-dev", "ORCA_DEV_REPO_ROOT is set"
    if sys.platform.startswith("linux"):
        ide = shutil.which("orca-ide")
        if ide:
            return ide, "orca-ide on PATH"
        # Where Orca's managed server installs its CLI on an SSH host (seen on the devbox,
        # 2026-11-12), and the folder Orca names in its terminals; neither is on a
        # non-interactive PATH.
        for folder in (os.environ.get("ORCA_CLI_BIN_DIR"),
                       os.path.join(os.environ.get("HOME", ""), ".orca", "cli", "bin")):
            if folder:
                cand = os.path.join(folder, "orca-ide")
                if os.path.isfile(cand) and os.access(cand, os.X_OK):
                    return cand, f"orca-ide in {folder}"
        bare = shutil.which("orca")
        inside = bool(os.environ.get("ORCA_TERMINAL_HANDLE") or os.environ.get("ORCA_WORKTREE_ID"))
        if bare and inside and os.path.realpath(bare) != "/usr/bin/orca":
            return bare, "orca inside an Orca-managed terminal"
        if bare and os.path.realpath(bare) == "/usr/bin/orca":
            return None, ("/usr/bin/orca is the GNOME screen reader, not Orca IDE; run inside an "
                          "Orca terminal on this host or install the orca-ide CLI")
        return None, "no Orca CLI here: open a terminal of this host from Orca IDE"
    bare = shutil.which("orca")
    if bare:
        return bare, "orca on PATH"
    return None, "orca is not on PATH (install Orca IDE and its CLI)"


def call(cli: str, args: list[str], timeout: float = 120) -> dict[str, Any]:
    """Run one Orca command with --json --full and return the parsed response."""
    proc = run([*shlex.split(cli), *args, "--json", "--full"], timeout=timeout)
    text = proc.stdout.strip()
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError:
        data = {}
    if proc.returncode != 0 or not data.get("ok", False):
        err = data.get("error") if isinstance(data, dict) else None
        detail = (f"{err.get('code')}: {err.get('message')}" if isinstance(err, dict)
                  else (proc.stderr.strip() or text or f"exit {proc.returncode}"))
        if isinstance(err, dict) and err.get("code") == "no_active_sender_terminal":
            # Seen live on Orca 1.4.256: orchestration needs to know which session is calling.
            detail += ("\n  Run this from the coordinator's own Orca terminal or chat (Orca sets "
                       "ORCA_TERMINAL_HANDLE there), or pass --from <your own terminal handle> "
                       "(orca terminal list --json). Nothing was created.")
        raise HarnessError(f"orca {' '.join(args[:2])} failed: {detail}")
    return data


def _q(s: str) -> str:
    return shlex.quote(s)


def build_commands(run_dir: Path) -> list[dict[str, Any]]:
    """The Orca calls that create this run's DAG, in dependency order. Task and gate calls refer to
    earlier results by harness task id; `create` substitutes the Orca ids as it goes."""
    info = load_run(run_dir)
    tasks = {t["id"]: t for t in info["tasks"]}
    order = dag.topological({tid: as_list(t.get("depends_on")) for tid, t in tasks.items()})
    objective = f"{info['title']} [{info['feature']} spec {info['spec_digest'][7:19]}]"
    steps: list[dict[str, Any]] = [{"kind": "run", "args": ["orchestration", "run-create",
                                                             "--objective", objective]}]
    for tid in order:
        t = tasks[tid]
        steps.append({
            "kind": "task",
            "id": tid,
            "deps": as_list(t.get("depends_on")),
            "args": ["orchestration", "task-create",
                     "--spec-file", str(run_dir / "briefs" / f"{tid}.md"),
                     "--task-title", f"{tid}: {t['title']}"],
        })
        if t.get("approval"):
            steps.append({
                "kind": "gate",
                "id": tid,
                "args": ["orchestration", "gate-create", "--question", str(t["approval"]),
                         "--options", json.dumps(["approve", "reject"])],
            })
    return steps


def render_script(steps: list[dict[str, Any]], cli: str = "orca") -> str:
    lines = ["# Orca calls tte-harness would make (dry run). <orca-id:X> is the id Orca returns",
             "# for harness task X; `tte-harness orca create --run-dir <dir>` makes the calls",
             "# and fills them in."]
    for s in steps:
        args = list(s["args"])
        if s["kind"] == "run":
            pass
        elif s["kind"] == "task":
            if s["deps"]:
                args += ["--deps", json.dumps([f"<orca-id:{d}>" for d in s["deps"]])]
            args += ["--run", "<orca-run-id>"]
        elif s["kind"] == "gate":
            args += ["--task", f"<orca-id:{s['id']}>"]
        lines.append(" ".join([cli, *(_q(a) for a in args), "--json", "--full"]))
    return "\n".join(lines) + "\n"


def create(run_dir: Path, cli: str, sender: str | None = None) -> dict[str, Any]:
    """Create the Run, its Tasks and gates in Orca, writing orca-map.json after every call so a
    failure part way leaves an exact record of what exists.

    `sender` is the caller's own terminal handle (`--from`); without it Orca identifies the
    caller from the Orca terminal or chat the command runs in."""
    extra = ["--from", sender] if sender else []
    map_path = run_dir / MAP_NAME
    if map_path.is_file():
        existing = read_json(map_path)
        if existing.get("complete"):
            raise HarnessError(f"{map_path}: this run already exists in Orca as "
                               f"{existing.get('run_id')}; not creating it twice")
        raise HarnessError(f"{map_path}: an earlier create stopped part way; inspect it and the "
                           "Run in Orca (orca orchestration run-show) before retrying by hand")
    mapping: dict[str, Any] = {"schema": 1, "run_id": None, "tasks": {}, "gates": {},
                               "complete": False}
    for step in build_commands(run_dir):
        args = list(step["args"]) + extra
        if step["kind"] == "run":
            res = call(cli, args)
            mapping["run_id"] = res["result"]["run"]["id"]
        elif step["kind"] == "task":
            if step["deps"]:
                args += ["--deps", json.dumps([mapping["tasks"][d] for d in step["deps"]])]
            args += ["--run", mapping["run_id"]]
            res = call(cli, args)
            mapping["tasks"][step["id"]] = res["result"]["task"]["id"]
        elif step["kind"] == "gate":
            args += ["--task", mapping["tasks"][step["id"]]]
            res = call(cli, args)
            mapping["gates"][step["id"]] = res["result"]["gate"]["id"]
        write_json(map_path, mapping)
    mapping["complete"] = True
    write_json(map_path, mapping)
    return mapping


def lifecycle(run_dir: Path, orca_tasks: list[dict[str, Any]],
              evidence: dict[str, tuple[bool, bool]]) -> dict[str, str]:
    """Map Orca task statuses onto the harness lifecycle (config/harness.yaml `states`).

    `orca_tasks` is `result.tasks` of `orca orchestration task-list --json --full`;
    `evidence[task]` is (development gates pass, all non-human gates pass) from
    `tte-harness evidence check`."""
    info = load_run(run_dir)
    mapping = read_json(run_dir / MAP_NAME) if (run_dir / MAP_NAME).is_file() else {"tasks": {}}
    by_orca = {str(t.get("id")): t for t in orca_tasks}
    status_of = {tid: str(by_orca.get(oid, {}).get("status", "missing"))
                 for tid, oid in mapping.get("tasks", {}).items()}
    out: dict[str, str] = {}
    for t in info["tasks"]:
        tid = t["id"]
        st = status_of.get(tid, "not-created")
        result = str(by_orca.get(mapping.get("tasks", {}).get(tid, ""), {}).get("result") or "")
        if st == "pending":
            out[tid] = "PENDING"
        elif st == "ready":
            out[tid] = "READY"
        elif st == "dispatched":
            out[tid] = "RUNNING"
        elif st == "blocked":
            out[tid] = "NEEDS_APPROVAL" if t.get("approval") else "BLOCKED"
        elif st == "failed":
            out[tid] = "CANCELLED" if result.strip().lower().startswith("cancelled") else "FAILED"
        elif st == "completed":
            dev_ok, all_ok = evidence.get(tid, (False, False))
            rb = t.get("review_by")
            if not dev_ok:
                out[tid] = "VALIDATING"
            elif (rb and status_of.get(rb) != "completed") or not all_ok:
                out[tid] = "REVIEW"
            else:
                out[tid] = "COMPLETED"
        else:
            out[tid] = st.upper()
    return out
