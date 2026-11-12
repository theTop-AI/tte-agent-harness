"""`tte-harness doctor`: check that this host can run the harness, with a fix for every failure."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .install import load_manifest, manifest_path
from .model import Harness
from .orca import resolve_cli
from .util import (
    agents_skills_dir,
    bin_dir,
    claude_config_dir,
    codex_home,
    git,
    run,
    sha256_file,
    state_dir,
)


@dataclass
class Check:
    name: str
    status: str  # OK, WARN, FAIL, SKIP
    detail: str
    fix: str = ""


def _ver(exe: str, args: list[str] | None = None) -> str | None:
    path = shutil.which(exe)
    if not path:
        return None
    try:
        proc = run([path, *(args or ["--version"])], timeout=30)
    except Exception:  # noqa: BLE001
        return "unknown"
    lines = (proc.stdout or proc.stderr).strip().splitlines()
    return lines[0] if lines else "unknown"


def _writable(path: Path) -> bool:
    probe = path
    while not probe.exists():
        probe = probe.parent
    return os.access(probe, os.W_OK)


def check_tools(checks: list[Check]) -> None:
    py = sys.version_info
    checks.append(Check("python", "OK" if py >= (3, 10) else "FAIL",
                        f"{sys.executable} {py.major}.{py.minor}.{py.micro}",
                        "" if py >= (3, 10) else "use Python 3.10 or newer"))
    for exe, fix in [("git", "sudo apt-get install git"),
                     ("gh", "install GitHub CLI: https://cli.github.com, then `gh auth login`")]:
        v = _ver(exe)
        checks.append(Check(exe, "OK" if v else "FAIL", v or "not on PATH", "" if v else fix))
    gv = _ver("git")
    if gv:
        m = re.search(r"(\d+)\.(\d+)", gv)
        ok = bool(m) and (int(m.group(1)), int(m.group(2))) >= (2, 17)
        checks.append(Check("git worktree", "OK" if ok else "FAIL", gv,
                            "" if ok else "git 2.17+ is needed for `git worktree` as Orca uses it"))
    if shutil.which("gh"):
        proc = run(["gh", "auth", "status"], timeout=30)
        ok = proc.returncode == 0
        checks.append(Check("gh auth", "OK" if ok else "FAIL",
                            "logged in" if ok else (proc.stderr.strip().splitlines() or ["?"])[0],
                            "" if ok else "gh auth login (scopes: repo, read:org, workflow)"))
    claude = _ver("claude")
    checks.append(Check("claude code", "OK" if claude else "FAIL", claude or "not on PATH",
                        "" if claude else "install Claude Code: "
                        "curl -fsSL https://claude.ai/install.sh | bash (review it first)"))
    codex = _ver("codex")
    checks.append(Check("codex", "OK" if codex else "WARN", codex or "not installed (optional)",
                        "" if codex else "optional: npm install -g @openai/codex, then codex login"))
    injected = os.environ.get("ORCA_CLAUDE_INJECTED_CONFIG_DIR")
    if injected:
        checks.append(Check("claude config dir", "WARN",
                            f"Orca injected CLAUDE_CONFIG_DIR={injected} (a managed account)",
                            "harness files in ~/.claude are not visible to this account: run "
                            "`tte-harness install` from this pane too, or pick System default"))
    for label, path in [("claude config", claude_config_dir()), ("agent skills", agents_skills_dir()),
                        ("codex home", codex_home()), ("state", state_dir()), ("bin", bin_dir())]:
        ok = _writable(path)
        checks.append(Check(f"path {label}", "OK" if ok else "FAIL", str(path),
                            "" if ok else f"make {path} writable by {os.environ.get('USER', 'you')}"))
    on_path = str(bin_dir()) in os.environ.get("PATH", "").split(os.pathsep)
    checks.append(Check("~/.local/bin on PATH", "OK" if on_path else "WARN", str(bin_dir()),
                        "" if on_path else "add `export PATH=\"$HOME/.local/bin:$PATH\"` to ~/.bashrc"))


def check_install(h: Harness, checks: list[Check]) -> None:
    manifest = load_manifest()
    if not manifest["files"]:
        checks.append(Check("harness installed", "FAIL", f"no manifest at {manifest_path()}",
                            "scripts/install.sh"))
        return
    missing = [p for p in manifest["files"] if not Path(p).is_file()]
    edited = [p for p, e in manifest["files"].items()
              if Path(p).is_file() and sha256_file(Path(p)) != e.get("sha256")]
    src = manifest.get("source") or {}
    head = git(["rev-parse", "HEAD"], h.root)
    status = "OK"
    detail = (f"{len(manifest['files'])} files from {src.get('describe') or src.get('commit')} "
              f"for {', '.join(manifest.get('providers') or [])}")
    fix = ""
    if missing or edited:
        status = "FAIL"
        detail += f"; {len(missing)} missing, {len(edited)} edited since install"
        fix = "scripts/install.sh (edited files are reported as conflicts; --force backs them up)"
    elif head and src.get("commit") and head != src.get("commit"):
        status = "WARN"
        detail += f"; the checkout is now at {head[:12]}"
        fix = "scripts/install.sh to install the checked-out revision"
    checks.append(Check("harness installed", status, detail, fix))
    skills_seen = {Path(p).parent.name for p in manifest["files"] if p.endswith("/SKILL.md")}
    lacking = sorted(set(h.skills) - skills_seen)
    checks.append(Check("skills discoverable", "OK" if not lacking else "FAIL",
                        f"{len(skills_seen)} skill folders with SKILL.md installed",
                        "" if not lacking else f"not installed: {', '.join(lacking)}"))


def check_orca(checks: list[Check]) -> None:
    cli, why = resolve_cli()
    if not cli:
        checks.append(Check("orca cli", "WARN", why,
                            "run doctor from a terminal Orca opened on this host"))
        return
    v = run([*cli.split(), "--version"], timeout=30)
    checks.append(Check("orca cli", "OK" if v.returncode == 0 else "FAIL",
                        f"{cli} ({why}) {v.stdout.strip()}"))
    guide = run([*cli.split(), "skills", "get", "orchestration", "--json"], timeout=30)
    checks.append(Check("orca orchestration guide", "OK" if guide.returncode == 0 else "FAIL",
                        "bundled guide readable" if guide.returncode == 0 else guide.stderr.strip(),
                        "" if guide.returncode == 0 else "update Orca (orca skills get is missing)"))
    for skill in ("orca-cli", "orchestration"):
        found = [d for d in (agents_skills_dir() / skill, claude_config_dir() / "skills" / skill)
                 if (d / "SKILL.md").is_file()]
        checks.append(Check(f"orca skill {skill}", "OK" if found else "WARN",
                            ", ".join(map(str, found)) or "not installed",
                            "" if found else "scripts/install.sh --with-orca-skills "
                            "(runs `orca skills install --skill orca-cli --skill orchestration`)"))
    status = run([*cli.split(), "status", "--json"], timeout=30)
    try:
        st = json.loads(status.stdout or "{}").get("result") or {}
    except json.JSONDecodeError:
        st = {}
    reachable = bool((st.get("runtime") or {}).get("reachable"))
    checks.append(Check("orca runtime", "OK" if reachable else "WARN",
                        f"runtime {(st.get('runtime') or {}).get('state', 'unknown')}",
                        "" if reachable else "open Orca (orca open) or run this inside an Orca "
                        "terminal; orchestration needs a reachable runtime"))
    if reachable:
        runs = run([*cli.split(), "orchestration", "run-list", "--json"], timeout=30)
        ok = runs.returncode == 0
        detail = "orchestration commands answer" if ok else (runs.stdout + runs.stderr).strip()[:300]
        checks.append(Check("orca orchestration", "OK" if ok else "FAIL", detail,
                            "" if ok else "Settings -> Experimental -> enable orchestration; on an "
                            "SSH host also Settings -> SSH -> <host> -> Advanced Connection -> "
                            "'Allow this host's orca CLI to control Orca' (see docs/orchestration.md)"))
    else:
        checks.append(Check("orca orchestration", "SKIP", "runtime not reachable"))


def check_repositories(h: Harness, checks: list[Check], remote: bool) -> None:
    for name, repo in h.repositories.items():
        path = repo.path
        if not path.is_dir():
            checks.append(Check(f"repo {name}", "WARN", f"{path} does not exist",
                                f"git clone https://github.com/{repo.github}.git {path} "
                                f"(or set its path in {h.repositories_file.name})"))
            continue
        top = git(["rev-parse", "--show-toplevel"], path)
        if not top:
            checks.append(Check(f"repo {name}", "FAIL", f"{path} is not a git checkout"))
            continue
        wt = git(["worktree", "list", "--porcelain"], path)
        project = path / ".claude" / "project.json"
        steps = []
        if project.is_file():
            try:
                steps = [s.get("name") for s in json.loads(project.read_text()).get("validate", [])]
            except (json.JSONDecodeError, AttributeError):
                steps = ["<invalid JSON>"]
        detail = (f"{path}; worktrees {'ok' if wt is not None else 'unavailable'}; validate: "
                  f"{', '.join(map(str, steps)) or 'none committed'}")
        checks.append(Check(f"repo {name}", "OK" if wt is not None else "FAIL", detail,
                            "" if project.is_file() else
                            "no .claude/project.json: repo-validate cannot pass here"))
        if remote and shutil.which("gh"):
            proc = run(["gh", "repo", "view", repo.github, "--json", "viewerPermission"], timeout=30)
            perm = None
            if proc.returncode == 0:
                perm = json.loads(proc.stdout).get("viewerPermission")
            ok = perm in {"WRITE", "MAINTAIN", "ADMIN"}
            checks.append(Check(f"github {repo.github}", "OK" if ok else "FAIL",
                                f"permission {perm or 'none'}",
                                "" if ok else "ask an org admin for write access"))


def doctor(h: Harness, remote: bool = True) -> list[Check]:
    checks: list[Check] = []
    check_tools(checks)
    check_install(h, checks)
    check_orca(checks)
    check_repositories(h, checks, remote)
    return checks


def render(checks: list[Check], as_json: bool) -> str:
    if as_json:
        return json.dumps([asdict(c) for c in checks], indent=2)
    width = max(len(c.name) for c in checks)
    out = []
    for c in checks:
        out.append(f"{c.status:4}  {c.name:{width}}  {c.detail}")
        if c.fix and c.status in {"FAIL", "WARN"}:
            out.append(f"{'':4}  {'':{width}}  fix: {c.fix}")
    return "\n".join(out)
