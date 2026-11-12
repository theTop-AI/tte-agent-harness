"""Command line: tte-harness <command>. Exit codes: 0 ok, 1 a check failed, 2 usage or
configuration error, 3 installed with conflicts left alone."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__, doctor as doctor_mod, evidence, feature, install, orca
from .model import Harness, find_root, load
from .util import HarnessError, expand, read_json
from .validate import validate


def _harness() -> Harness:
    return load(find_root(Path.cwd()))


def _run_dir(args: argparse.Namespace, h: Harness, feature_name: str | None = None) -> Path:
    raw = getattr(args, "run_dir", None) or os.environ.get("TTE_HARNESS_RUN_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    if feature_name:
        return expand(str(h.config["runs"]["root"])) / feature_name
    raise HarnessError("--run-dir is required (or set TTE_HARNESS_RUN_DIR); the task brief names it")


def cmd_validate(args: argparse.Namespace) -> int:
    h = _harness()
    f = validate(h)
    for item in f.items:
        if item.level == "error" or args.warnings:
            print(item)
    print(f"{len(h.agents)} agents, {len(h.skills)} skills, {len(h.workflows)} workflows, "
          f"{len(h.gates)} gates, {len(h.repositories)} repositories "
          f"({h.repositories_file.name}): {len(f.errors)} errors, {len(f.warnings)} warnings")
    return 1 if f.errors else 0


def cmd_install(args: argparse.Namespace) -> int:
    h = _harness()
    f = validate(h)
    if f.errors:
        for e in f.errors:
            print(e, file=sys.stderr)
        raise HarnessError("the harness source does not validate; nothing installed")
    providers = install.detect_providers(args.providers.split(",") if args.providers else None)
    source = install.source_info(h, args.allow_dirty, args.ref)
    plan = install.plan_install(h, providers, source, args.force, not args.no_cli,
                                args.with_permissions)
    print(f"source     {source['path']} @ {source.get('describe') or source.get('commit')}"
          + (" (dirty)" if source.get("dirty") else ""))
    for name, info in providers.items():
        print(f"provider   {name}: {info['version'] or 'binary not found'}; config {info['config']}")
    for a in plan.actions:
        if a.op == "unchanged" and not args.verbose:
            continue
        print(f"{a.op:13} {a.path}" + (f"  ({a.detail})" if a.detail else ""))
    if plan.permissions is not None:
        for kind, rules in plan.permissions["add"].items():
            for r in rules:
                print(f"{'permission':13} {plan.permissions['settings']} {kind}: {r}")
        if not plan.permissions["add"]:
            print(f"{'permission':13} {plan.permissions['settings']}: every rule already present")
    counts = {op: plan.count(op) for op in
              ("create", "update", "unchanged", "conflict", "force", "remove", "keep-modified")}
    summary = ", ".join(f"{n} {op}" for op, n in counts.items() if n)
    if args.dry_run:
        print(f"dry run: nothing written ({summary or 'no changes'})")
        if args.with_orca_skills:
            print(install.orca_skills(dry_run=True))
        return 0
    install.apply(plan)
    print(f"installed: {summary or 'no changes'}; manifest {install.manifest_path()}")
    if args.with_orca_skills:
        print(install.orca_skills(dry_run=False))
    if counts["conflict"]:
        print("conflicts were left alone: resolve them, or rerun with --force (backs them up to "
              f"{install.state_dir() / 'backups'})", file=sys.stderr)
        return 3
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    for line in install.uninstall(args.dry_run):
        print(line)
    if args.dry_run:
        print("dry run: nothing removed")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    h = _harness()
    checks = doctor_mod.doctor(h, remote=not args.offline)
    print(doctor_mod.render(checks, args.json))
    return 1 if any(c.status == "FAIL" for c in checks) else 0


def cmd_repos(args: argparse.Namespace) -> int:
    h = _harness()
    for name, repo in h.repositories.items():
        project = repo.path / ".claude" / "project.json"
        steps = "unknown (no checkout here)"
        if project.is_file():
            data = read_json(project)
            steps = "; ".join(f"{s.get('name')}: {s.get('run')}" for s in data.get("validate", []))
        elif repo.path.is_dir():
            steps = "none committed (.claude/project.json missing)"
        print(f"{name}  {repo.github}  {repo.path}\n  roles: {', '.join(repo.roles)}\n"
              f"  contract: {', '.join(repo.contract_paths) or '-'}\n  validate: {steps}")
    return 0


def cmd_spec(args: argparse.Namespace) -> int:
    spec_dir = Path(args.spec_dir).resolve()
    if args.spec_cmd == "lock":
        lock = feature.lock_spec(spec_dir, args.feature or spec_dir.parent.name,
                                 args.approved_by, args.note or "")
        print(f"locked {spec_dir} {lock['digest']} ({len(lock['files'])} files, approved by "
              f"{lock['approved_by']})")
        return 0
    lock, diffs = feature.verify_spec(spec_dir)
    if diffs:
        print("\n".join(diffs))
        print(f"spec does NOT match its lock {lock.get('digest')}")
        return 1
    print(f"spec matches its lock {lock['digest']} (approved by {lock.get('approved_by')})")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    h = _harness()
    plan = feature.load_plan(Path(args.plan))
    f = feature.validate_plan(h, plan)
    for item in f.items:
        print(item)
    if f.errors:
        return 1
    if args.check:
        print(f"{plan.path}: valid, {len(plan.tasks)} tasks")
        return 0
    run_dir = _run_dir(args, h, plan.feature)
    summary = feature.prepare_run(h, plan, run_dir)
    print(f"run {run_dir}\nspec {summary['spec_digest']}")
    for i, wave in enumerate(summary["waves"], 1):
        print(f"wave {i}: {', '.join(wave)}" + ("  (parallel)" if len(wave) > 1 else ""))
    print(f"briefs: {run_dir / 'briefs'}\nnext: tte-harness orca commands --run-dir {run_dir}")
    return 0


def cmd_orca(args: argparse.Namespace) -> int:
    h = _harness()
    run_dir = _run_dir(args, h)
    if args.orca_cmd == "commands":
        print(orca.render_script(orca.build_commands(run_dir)), end="")
        return 0
    cli, why = orca.resolve_cli()
    if not cli:
        raise HarnessError(f"no Orca CLI: {why}")
    mapping = orca.create(run_dir, cli)
    print(f"Run {mapping['run_id']}: {len(mapping['tasks'])} tasks, {len(mapping['gates'])} gates "
          f"-> {run_dir / orca.MAP_NAME}")
    return 0


def _evidence_flags(h: Harness, run_dir: Path, task: dict) -> tuple[bool, bool]:
    rows = evidence.check_task(h, run_dir, task["id"])
    # Only mechanical gates a worker can satisfy alone decide VALIDATING; a review-kind gate is
    # the reviewer's to attest, whatever its stage.
    dev_gates = {g for g, spec in h.gates.items()
                 if spec.get("stage") == "development" and spec.get("kind") == "evidence"}
    dev_ok = all(r != "FAIL" for g, r, _ in rows if g in dev_gates)
    all_ok = all(r != "FAIL" for _, r, _ in rows)
    return dev_ok, all_ok


def cmd_status(args: argparse.Namespace) -> int:
    h = _harness()
    run_dir = _run_dir(args, h)
    info = feature.load_run(run_dir)
    if args.orca_json:
        data = json.loads(Path(args.orca_json).read_text())
    else:
        cli, why = orca.resolve_cli()
        if not cli:
            raise HarnessError(f"no Orca CLI ({why}); pass --orca-json <saved task-list output>")
        mapping = read_json(run_dir / orca.MAP_NAME)
        data = orca.call(cli, ["orchestration", "task-list", "--run", mapping["run_id"]])
    tasks = (data.get("result") or {}).get("tasks") or []
    flags = {t["id"]: _evidence_flags(h, run_dir, t) for t in info["tasks"]}
    states = orca.lifecycle(run_dir, tasks, flags)
    for t in info["tasks"]:
        print(f"{states[t['id']]:15} {t['id']:28} {t['role']:22} {t['repo']}")
    return 0


def cmd_evidence(args: argparse.Namespace) -> int:
    h = _harness()
    run_dir = _run_dir(args, h)
    if args.ev_cmd == "run":
        rec = evidence.run_validation(h, run_dir, args.task, Path(args.repo_dir).resolve(),
                                      args.base, args.dry_run)
        for s in rec["steps"]:
            if args.dry_run:
                print(f"{'run' if s['would_run'] else 'skip':5} {s['name']}: {s['run']}")
            elif s.get("skipped"):
                print(f"SKIP  {s['name']} ({s['reason']})")
            else:
                print(f"{'PASS' if s['exit_code'] == 0 else 'FAIL'}  {s['name']} "
                      f"({s['seconds']}s, {s['log']})")
        print(f"head {rec['head']} dirty={rec['dirty']} contract_changed={rec['contract_changed']} "
              f"secrets={len(rec['secret_hits'])}")
        if rec["validation_source"] is None:
            print("no .claude/project.json in this repository: nothing to run", file=sys.stderr)
            return 1
        failed = [s for s in rec["steps"] if not s.get("skipped") and s.get("exit_code") not in (0, None)]
        return 1 if failed or rec["secret_hits"] else 0
    if args.ev_cmd == "review":
        attest = [g for g in (args.attest or "").split(",") if g]
        for g in attest:
            if g not in h.gates or h.gates[g].get("kind") != "review":
                raise HarnessError(f"--attest {g}: not a review-kind gate")
        rec = evidence.record_review(run_dir, args.task, Path(args.repo_dir).resolve(),
                                     args.verdict, args.critical,
                                     Path(args.findings) if args.findings else None,
                                     attest, args.reviewer or "")
        print(f"review {rec['verdict']} on {rec['head']} recorded for {args.task}")
        return 0
    if args.ev_cmd == "pr":
        rec = evidence.record_pr(run_dir, args.task, args.pr)
        print(f"pr {rec['url']} head {rec['head']} ci_green={rec['ci_green']}")
        return 0
    rows = evidence.check_task(h, run_dir, args.task)
    if args.json:
        print(json.dumps([{"gate": g, "result": r, "reason": why} for g, r, why in rows], indent=2))
    else:
        for g, r, why in rows:
            print(f"{r:5}  {g:22} {why}")
    return 1 if any(r == "FAIL" for _, r, _ in rows) else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tte-harness", description=__doc__)
    p.add_argument("--version", action="version", version=f"tte-harness {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="check agents, skills, workflows, configs, examples")
    v.add_argument("--warnings", action="store_true", help="print warnings too")
    v.set_defaults(func=cmd_validate)

    i = sub.add_parser("install", help="install agents and skills for Claude Code and Codex")
    i.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    i.add_argument("--providers", help="claude,codex (default: those found on this host)")
    i.add_argument("--force", action="store_true", help="replace conflicts after backing them up")
    i.add_argument("--allow-dirty", action="store_true", help="install an uncommitted checkout")
    i.add_argument("--ref", help="refuse unless the checkout is at this tag or commit")
    i.add_argument("--no-cli", action="store_true", help="do not install ~/.local/bin/tte-harness")
    i.add_argument("--with-permissions", action="store_true",
                   help="add adapters/claude-code/permissions.json rules to Claude settings.json")
    i.add_argument("--with-orca-skills", action="store_true",
                   help="also run `orca skills install --skill orca-cli --skill orchestration`")
    i.add_argument("--verbose", action="store_true", help="list unchanged files too")
    i.set_defaults(func=cmd_install)

    u = sub.add_parser("uninstall", help="remove what install wrote, keeping edited files")
    u.add_argument("--dry-run", action="store_true")
    u.set_defaults(func=cmd_uninstall)

    d = sub.add_parser("doctor", help="diagnose this host")
    d.add_argument("--json", action="store_true")
    d.add_argument("--offline", action="store_true", help="skip GitHub permission checks")
    d.set_defaults(func=cmd_doctor)

    r = sub.add_parser("repos", help="show repositories and their live validation sequence")
    r.set_defaults(func=cmd_repos)

    s = sub.add_parser("spec", help="lock or verify an approved spec")
    ssub = s.add_subparsers(dest="spec_cmd", required=True)
    sl = ssub.add_parser("lock")
    sl.add_argument("spec_dir")
    sl.add_argument("--approved-by", required=True)
    sl.add_argument("--feature")
    sl.add_argument("--note")
    sv = ssub.add_parser("verify")
    sv.add_argument("spec_dir")
    s.set_defaults(func=cmd_spec)

    pl = sub.add_parser("plan", help="validate a feature plan and prepare its run folder")
    pl.add_argument("plan")
    pl.add_argument("--run-dir")
    pl.add_argument("--check", action="store_true", help="validate only")
    pl.set_defaults(func=cmd_plan)

    o = sub.add_parser("orca", help="create the run's task DAG in Orca")
    osub = o.add_subparsers(dest="orca_cmd", required=True)
    for name in ("commands", "create"):
        x = osub.add_parser(name)
        x.add_argument("--run-dir")
    o.set_defaults(func=cmd_orca)

    st = sub.add_parser("status", help="lifecycle state of every task, from Orca and evidence")
    st.add_argument("--run-dir")
    st.add_argument("--orca-json", help="a saved `orca orchestration task-list --json --full`")
    st.set_defaults(func=cmd_status)

    e = sub.add_parser("evidence", help="record and check task evidence")
    esub = e.add_subparsers(dest="ev_cmd", required=True)
    er = esub.add_parser("run", help="run the repository's validation sequence and record it")
    er.add_argument("--base", help="base ref (default origin/<baseBranch>)")
    er.add_argument("--dry-run", action="store_true")
    ev = esub.add_parser("review", help="record a reviewer's verdict")
    ev.add_argument("--verdict", required=True, choices=["pass", "fail"])
    ev.add_argument("--critical", type=int, required=True)
    ev.add_argument("--findings")
    ev.add_argument("--attest", help="comma-separated review-kind gates the reviewer checked")
    ev.add_argument("--reviewer")
    ep = esub.add_parser("pr", help="record the pull request and its checks")
    ep.add_argument("--pr", required=True)
    ec = esub.add_parser("check", help="decide every gate of the task")
    ec.add_argument("--json", action="store_true")
    for x in (er, ev, ep, ec):
        x.add_argument("--run-dir")
        x.add_argument("--task", required=True)
    for x in (er, ev):
        x.add_argument("--repo-dir", default=".")
    e.set_defaults(func=cmd_evidence)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except HarnessError as exc:
        print(f"tte-harness: {exc}", file=sys.stderr)
        return 2
