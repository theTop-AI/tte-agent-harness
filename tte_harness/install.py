"""Install, update and uninstall the harness into a user's Claude Code and Codex configuration.

Ownership is explicit: every file the harness writes is recorded, with its hash, in
<state>/install-manifest.json. A destination the manifest does not own, or one a person edited
after the install, is a conflict and is left alone unless --force, which first backs it up.
Uninstall removes only files that are still exactly as installed. A dry run writes nothing at all.

Targets (verified against the tools' docs, 2026-11):
  Claude Code  <CLAUDE_CONFIG_DIR or ~/.claude>/skills/<name>/   and   .../agents/<name>.md
  Codex        ~/.agents/skills/<name>/                           and   <CODEX_HOME or ~/.codex>/agents/<name>.toml
  CLI          ~/.local/bin/tte-harness (runs this checkout's bin/tte-harness)
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import __version__
from .model import Harness
from .orca import resolve_cli
from .render import claude_agent, codex_agent
from .util import (
    HarnessError,
    agents_skills_dir,
    bin_dir,
    claude_config_dir,
    codex_home,
    git,
    home,
    iter_files,
    read_json,
    run,
    sha256_bytes,
    sha256_file,
    state_dir,
    write_json,
)

PROVIDERS = ("claude", "codex")
MANIFEST = "install-manifest.json"


@dataclass
class Target:
    path: Path
    content: bytes
    unit: str  # e.g. "claude skill api-design"
    unit_root: Path  # the skill folder, or the file itself for agents and the CLI
    mode: int = 0o644


@dataclass
class Action:
    op: str  # create, update, unchanged, conflict, force, remove, keep-modified, forget
    path: Path
    unit: str
    detail: str = ""


@dataclass
class Plan:
    source: dict[str, Any]
    providers: dict[str, dict[str, Any]]
    actions: list[Action] = field(default_factory=list)
    targets: dict[Path, Target] = field(default_factory=dict)
    permissions: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)

    def count(self, op: str) -> int:
        return sum(1 for a in self.actions if a.op == op)


def manifest_path() -> Path:
    return state_dir() / MANIFEST


def load_manifest() -> dict[str, Any]:
    path = manifest_path()
    if path.is_file():
        data = read_json(path)
        data.setdefault("files", {})
        return data
    return {"schema": 1, "files": {}}


# --- environment ------------------------------------------------------------------------------

def _version(cmd: str) -> str | None:
    exe = shutil.which(cmd)
    if not exe:
        return None
    try:
        proc = run([exe, "--version"], timeout=20)
    except Exception:  # noqa: BLE001 - any failure means "unknown"
        return "unknown"
    out = (proc.stdout or proc.stderr).strip().splitlines()
    return out[0] if out else "unknown"


def detect_providers(requested: list[str] | None) -> dict[str, dict[str, Any]]:
    found = {
        "claude": {"version": _version("claude"), "config": str(claude_config_dir()),
                   "config_exists": claude_config_dir().is_dir()},
        "codex": {"version": _version("codex"), "config": str(codex_home()),
                  "config_exists": codex_home().is_dir()},
    }
    if requested:
        unknown = set(requested) - set(PROVIDERS)
        if unknown:
            raise HarnessError(f"unknown provider(s) {sorted(unknown)}; choose from {PROVIDERS}")
        chosen = list(requested)
    else:
        chosen = [p for p in PROVIDERS if found[p]["version"] or found[p]["config_exists"]]
        if not chosen:
            raise HarnessError("found neither Claude Code nor Codex (no binary, no config folder); "
                               "install one, or name the target with --providers claude,codex")
    return {p: found[p] for p in chosen}


def source_info(h: Harness, allow_dirty: bool, ref: str | None) -> dict[str, Any]:
    commit = git(["rev-parse", "HEAD"], h.root)
    info: dict[str, Any] = {"path": str(h.root), "version": __version__, "commit": commit,
                            "describe": None, "dirty": None}
    if commit is None:
        if ref:
            raise HarnessError("--ref needs a git checkout of the harness")
        info["note"] = "not a git checkout: the installed revision cannot be verified"
        return info
    info["describe"] = git(["describe", "--tags", "--always", "--dirty"], h.root)
    dirty = bool((git(["status", "--porcelain"], h.root) or "").strip())
    info["dirty"] = dirty
    if ref:
        want = git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], h.root)
        if not want:
            raise HarnessError(f"--ref {ref}: no such revision in {h.root} (git fetch --tags?)")
        if want != commit:
            raise HarnessError(f"the checkout is at {commit[:12]}, not {ref} ({want[:12]}); run "
                               f"`git -C {h.root} checkout {ref}` first")
    if dirty and not allow_dirty:
        raise HarnessError("the harness checkout has uncommitted changes, so what would be "
                           "installed is no commit; commit or stash them, or pass --allow-dirty")
    return info


# --- desired state ----------------------------------------------------------------------------

def desired_targets(h: Harness, providers: list[str], rev: str, with_cli: bool) -> list[Target]:
    out: list[Target] = []
    skill_roots = {"claude": claude_config_dir() / "skills", "codex": agents_skills_dir()}
    agent_roots = {"claude": claude_config_dir() / "agents", "codex": codex_home() / "agents"}
    for provider in providers:
        for name, skill in sorted(h.skills.items()):
            root = skill_roots[provider] / name
            for src in iter_files(skill.path):
                out.append(Target(root / src.relative_to(skill.path), src.read_bytes(),
                                  f"{provider} skill {name}", root))
        for name, agent in sorted(h.agents.items()):
            if provider == "claude":
                dest = agent_roots[provider] / f"{name}.md"
                text = claude_agent(h, agent, rev)
            else:
                dest = agent_roots[provider] / f"{name}.toml"
                text = codex_agent(h, agent, rev)
            out.append(Target(dest, text.encode(), f"{provider} agent {name}", dest))
    if with_cli:
        dest = bin_dir() / "tte-harness"
        script = ("#!/bin/sh\n# Installed by tte-agent-harness: runs the CLI of this checkout.\n"
                  f'exec "{h.root / "bin" / "tte-harness"}" "$@"\n')
        out.append(Target(dest, script.encode(), "cli tte-harness", dest, 0o755))
    return out


def _owned_unchanged(manifest: dict[str, Any], path: Path) -> bool:
    entry = manifest["files"].get(str(path))
    return bool(entry) and path.is_file() and sha256_file(path) == entry.get("sha256")


def plan_install(h: Harness, providers: dict[str, dict[str, Any]], source: dict[str, Any],
                 force: bool, with_cli: bool, with_permissions: bool) -> Plan:
    manifest = load_manifest()
    rev = (source.get("describe") or source.get("commit") or "unversioned")
    plan = Plan(source=source, providers=providers)
    targets = desired_targets(h, list(providers), rev, with_cli)
    plan.targets = {t.path: t for t in targets}

    # A skill folder that exists with a SKILL.md the harness does not own belongs to someone else:
    # never mix our files into it.
    foreign_units: set[str] = set()
    for t in targets:
        if t.unit_root.is_dir() and t.unit_root != t.path:
            skill_md = t.unit_root / "SKILL.md"
            ours = plan.targets.get(skill_md)
            if skill_md.is_file() and not _owned_unchanged(manifest, skill_md) and not (
                    ours and sha256_file(skill_md) == sha256_bytes(ours.content)):
                foreign_units.add(t.unit)

    for t in targets:
        want = sha256_bytes(t.content)
        exists = t.path.exists() or t.path.is_symlink()
        if t.unit in foreign_units and not force:
            plan.actions.append(Action("conflict", t.path, t.unit,
                                       "the folder holds a skill the harness did not install"))
        elif not exists:
            plan.actions.append(Action("create", t.path, t.unit))
        elif t.path.is_symlink() or not t.path.is_file():
            plan.actions.append(Action("force" if force else "conflict", t.path, t.unit,
                                       "a symlink or directory is in the way"))
        elif sha256_file(t.path) == want:
            plan.actions.append(Action("unchanged", t.path, t.unit))
        elif _owned_unchanged(manifest, t.path):
            plan.actions.append(Action("update", t.path, t.unit))
        else:
            why = ("edited since the harness installed it" if str(t.path) in manifest["files"]
                   else "not installed by the harness")
            plan.actions.append(Action("force" if force else "conflict", t.path, t.unit, why))

    for path_str, entry in sorted(manifest["files"].items()):
        path = Path(path_str)
        if path in plan.targets:
            continue
        if not path.exists():
            plan.actions.append(Action("forget", path, entry.get("unit", "?"), "already gone"))
        elif path.is_file() and sha256_file(path) == entry.get("sha256"):
            plan.actions.append(Action("remove", path, entry.get("unit", "?"),
                                       "no longer shipped by the harness"))
        else:
            plan.actions.append(Action("keep-modified", path, entry.get("unit", "?"),
                                       "no longer shipped, but edited locally: left in place"))

    if with_permissions:
        plan.permissions = plan_permissions(h, manifest)
    return plan


# --- Claude Code permissions (opt-in) ---------------------------------------------------------

def permissions_fragment(h: Harness) -> dict[str, list[str]]:
    data = json.loads((h.root / "adapters" / "claude-code" / "permissions.json").read_text())
    return {k: list(data.get(k, [])) for k in ("deny", "ask")}


def settings_path() -> Path:
    return claude_config_dir() / "settings.json"


def plan_permissions(h: Harness, manifest: dict[str, Any]) -> dict[str, Any]:
    path = settings_path()
    current: dict[str, Any] = {}
    if path.is_file():
        try:
            current = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise HarnessError(f"{path} is not valid JSON ({exc}); fix it before "
                               "--with-permissions touches it") from exc
    perms = current.get("permissions") or {}
    add: dict[str, list[str]] = {}
    for kind, rules in permissions_fragment(h).items():
        have = set(perms.get(kind) or [])
        new = [r for r in rules if r not in have]
        if new:
            add[kind] = new
    previous = (manifest.get("permissions") or {}).get("added") or {}
    return {"settings": str(path), "add": add, "previous": previous,
            "file_existed": path.is_file()}


def _apply_permissions(perm: dict[str, Any], backups: Path, manifest: dict[str, Any]) -> None:
    path = Path(perm["settings"])
    current: dict[str, Any] = {}
    if path.is_file():
        current = json.loads(path.read_text(encoding="utf-8") or "{}")
        if perm["add"]:
            backups.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backups / "settings.json")
    if perm["add"]:
        perms = current.setdefault("permissions", {})
        for kind, rules in perm["add"].items():
            perms.setdefault(kind, [])
            perms[kind].extend(rules)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    prev = manifest.get("permissions") or {}
    added = {k: list(v) for k, v in (prev.get("added") or {}).items()}
    for kind, rules in perm["add"].items():
        added.setdefault(kind, []).extend(r for r in rules if r not in added.get(kind, []))
    manifest["permissions"] = {
        "settings": str(path),
        "added": added,
        "created_file": prev.get("created_file", not perm["file_existed"]),
    }


def _remove_permissions(manifest: dict[str, Any], dry_run: bool) -> list[str]:
    perm = manifest.get("permissions")
    if not perm:
        return []
    path = Path(perm["settings"])
    if not path.is_file():
        return [f"forget      {path} (permissions; the file is gone)"]
    current = json.loads(path.read_text(encoding="utf-8") or "{}")
    perms = current.get("permissions") or {}
    lines = []
    for kind, rules in (perm.get("added") or {}).items():
        have = perms.get(kind) or []
        for r in rules:
            if r in have:
                lines.append(f"remove      {path} permissions.{kind}: {r}")
        perms[kind] = [r for r in have if r not in rules]
        if not perms[kind]:
            perms.pop(kind)
    if not perms:
        current.pop("permissions", None)
    if not dry_run:
        if not current and perm.get("created_file"):
            path.unlink()
            lines.append(f"remove      {path} (created by the harness, now empty)")
        else:
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, path)
    return lines


# --- apply ------------------------------------------------------------------------------------

def _backup_dir() -> Path:
    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    return state_dir() / "backups" / stamp


def _backup(path: Path, backups: Path) -> None:
    try:
        rel = path.relative_to(home())
    except ValueError:
        rel = Path(*path.parts[1:])
    dest = backups / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir() and not path.is_symlink():
        shutil.move(str(path), str(dest))
    elif path.is_symlink():
        dest.write_text(f"symlink -> {os.readlink(path)}\n")
        path.unlink()
    else:
        shutil.move(str(path), str(dest))


def _prune(path: Path, stop: Path) -> None:
    """Remove empty folders from path's parent up to and including stop (a unit root)."""
    cur = path.parent
    while True:
        try:
            cur.rmdir()
        except OSError:
            return
        if cur == stop:
            return
        cur = cur.parent


def apply(plan: Plan) -> dict[str, Any]:
    manifest = load_manifest()
    backups = _backup_dir()
    for a in plan.actions:
        t = plan.targets.get(a.path)
        if a.op in {"create", "update", "force"} and t is not None:
            if a.op == "force" and (a.path.exists() or a.path.is_symlink()):
                _backup(a.path, backups)
            a.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = a.path.with_name(a.path.name + ".tte-harness.tmp")
            tmp.write_bytes(t.content)
            tmp.chmod(t.mode)
            os.replace(tmp, a.path)
        if a.op in {"create", "update", "force", "unchanged"} and t is not None:
            manifest["files"][str(a.path)] = {"sha256": sha256_bytes(t.content), "unit": t.unit}
        elif a.op == "remove":
            unit_root = Path(manifest["files"][str(a.path)].get("root", a.path.parent))
            a.path.unlink()
            _prune(a.path, unit_root)
            manifest["files"].pop(str(a.path), None)
        elif a.op in {"keep-modified", "forget"}:
            manifest["files"].pop(str(a.path), None)
    for a in plan.actions:
        t = plan.targets.get(a.path)
        if t is not None and str(a.path) in manifest["files"]:
            manifest["files"][str(a.path)]["root"] = str(t.unit_root)
    if plan.permissions is not None:
        _apply_permissions(plan.permissions, backups, manifest)
    manifest.update(schema=1, source=plan.source, providers=plan.providers,
                    installed_at=_dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
                    .isoformat())
    write_json(manifest_path(), manifest)
    return manifest


def orca_skills(dry_run: bool) -> str:
    """Install Orca's official orca-cli and orchestration skills with Orca's own installer."""
    cli, why = resolve_cli()
    if not cli:
        return f"orca skills: skipped - {why}"
    args = [*cli.split(), "skills", "install", "--skill", "orca-cli", "--skill", "orchestration"]
    if dry_run:
        args.append("--dry-run")
    proc = run(args, timeout=120)
    out = (proc.stdout or proc.stderr).strip()
    status = "ok" if proc.returncode == 0 else f"exit {proc.returncode}"
    return f"orca skills ({' '.join(args)}): {status}\n{out}"


def uninstall(dry_run: bool) -> list[str]:
    manifest = load_manifest()
    lines: list[str] = []
    if not manifest["files"] and not manifest.get("permissions"):
        return ["nothing installed (no manifest at " + str(manifest_path()) + ")"]
    for path_str, entry in sorted(manifest["files"].items()):
        path = Path(path_str)
        if not path.exists():
            lines.append(f"forget      {path} (already gone)")
        elif path.is_file() and sha256_file(path) == entry.get("sha256"):
            lines.append(f"remove      {path}")
            if not dry_run:
                path.unlink()
                _prune(path, Path(entry.get("root", path.parent)))
        else:
            lines.append(f"keep        {path} (edited after install; yours now)")
    lines.extend(_remove_permissions(manifest, dry_run))
    if not dry_run:
        manifest_path().unlink()
        lines.append(f"remove      {manifest_path()}")
    return lines
