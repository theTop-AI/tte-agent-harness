# Orchestration with Orca

Orca IDE is the orchestrator: it creates worktrees, launches agents, holds the task DAG, carries
mail between agents, and blocks tasks on decision gates. The harness does not run agents. It turns
an approved plan into Orca's task DAG, gives every worker a self-contained brief, and decides from
recorded evidence whether a task is really done.

Facts here come from Orca 1.4.256 on the developer's Mac (`orca agent-context`, the bundled
guide `orca skills get orchestration --full`, the CLI handlers) and orca.dev/docs, read
2026-11-12. Orca changes fast; when this page and `orca skills get orchestration` disagree, the
guide that ships with the installed Orca wins.

## Four things that are not the same

| Thing | What it is | What it isolates |
|---|---|---|
| Orca worker | a top-level Claude Code or Codex session Orca launches for one Task, in its own worktree, reporting through Orca mail (`worker_done`, `ask`) | the working directory and the conversation |
| Claude Code / Codex subagent | a helper inside one session (`~/.claude/agents/*.md`, `~/.codex/agents/*.toml`), sharing that session's directory and permissions | the conversation only |
| Skill | instructions loaded into whichever session uses it | nothing: it is text |
| Git worktree | a second checkout of a repository on another branch | files on disk; not ports, databases, Docker, caches or credentials |

Two workers in two worktrees of the same repository still share the host's Docker daemon, ports
and test database. Tasks that start services (tte-engine's `make test-up`) must not run in
parallel on one host unless the repository isolates them; the plan serialises them with
`depends_on` when it does not. Sessions never share context: everything a worker needs is in its
brief, and everything it produces comes back through Orca mail and the run folder.

## Where things run

```
Mac (Orca IDE desktop)                    tte-devbox-vlad (EC2, Ubuntu 24.04, via SSM SSH)
──────────────────────                    ───────────────────────────────────────────────
editor, diffs, review UI       ──SSH──▶   Orca managed server (installed by Orca over SSH)
Orca runtime + settings                   ├─ /home/ubuntu/projects/<repo>      shared checkouts
                                          ├─ /home/ubuntu/orca/workspaces/     Orca worktrees
                                          ├─ coordinator session (Claude Code)
                                          ├─ worker sessions (Claude Code / Codex), one per Task
                                          └─ ~/.local/state/tte-agent-harness/runs/<feature>/
                                               spec/ (read-only), briefs/, evidence/, orca-map.json
```

An SSH workspace keeps the runtime with the desktop and runs worktrees, terminals and agents on
the host; Orca installs and updates its managed server there on first connection (Settings →
Managed servers). A *Remote Orca Server* (`orca serve` + pairing) is the other model, where the
server owns the whole runtime; v1 does not need it.

## Activating Orca orchestration

Each step says what it changes. None is done automatically by the harness.

1. **Log in to AWS for the SSM proxy** on the Mac: `aws sso login --profile tte-dev`.
   `ssh tte-devbox-vlad true` must succeed before Orca can connect.
2. **Enable orchestration**: Orca → Settings → Experimental → orchestration on. Orchestration is
   experimental in Orca; without this, `orca orchestration ...` is refused.
3. **Add the host**: Settings → SSH → *Add Target* → open the *OpenSSH config* picker → choose
   `tte-devbox-vlad` → *Test* → *Save*. The picker reads `~/.ssh/config`; the host uses a
   `ProxyCommand` (`aws ssm start-session`). The docs mention proxies only under *Advanced
   Connection*; if *Test* fails, set the proxy there. **Unverified until tried.**
4. **Register the repositories on the host** through the desktop (SSH project setups are made
   in the UI: add project → choose the SSH host → existing folder
   `/home/ubuntu/projects/tte-engine`, and the same for `tte-frontend`). Put their worktrees under
   `/home/ubuntu/orca/workspaces/`: the CLI has
   `orca project setup-update --setup <setup-id> --worktree-base-path /home/ubuntu/orca/workspaces`
   (setup ids from `orca project setups --json`). **Unverified until tried.**
5. **Install the harness on the host** (in a terminal Orca opens on the host, so `orca` resolves to
   Orca and not to `/usr/bin/orca`): see [getting-started.md](getting-started.md). Include
   `--with-orca-skills`, which runs `orca skills install --skill orca-cli --skill orchestration`.
6. **Allow the coordinator's host to drive Orca** — only if you run the coordinator on the host,
   which v1 does: Settings → SSH → edit `tte-devbox-vlad` → *Advanced Connection* → *Allow this
   host's orca CLI to control Orca*. Read the trade-off below before turning it on.
7. **Check**: from an Orca terminal on the host, `scripts/doctor.sh`. `orca orchestration` must
   say OK; every FAIL prints its fix.

### The SSH control permission: what it grants

By default an `orca` command run on an SSH host reaches only that host's own terminals and
orchestration mail: a worker there can still `ask` and report `worker_done` to the coordinator
that dispatched it. It cannot create worktrees, open terminals, launch agents or dispatch work.
That default is exactly right for worker-only hosts.

The coordinator has to create worktrees and start workers, so the host it runs on needs
*Allow this host's orca CLI to control Orca*. That permission is per host, not per session: once
on, **every** agent on that host, including a worker that read a prompt-injected issue, can create
worktrees, launch more agents and dispatch work through `orca`. Orca's docs state the scope and no
further limits. Mitigations in place:

- the harness permission rules deny `orca orchestration reset` and ask before `orca worktree rm`
  and plugin installs (`--with-permissions`);
- workers have no AWS, merge or force-push ability (deny rules, branch protection), so spawning
  more agents does not reach production;
- everything an agent starts is visible in Orca's workspace list and Run;
- turn the permission off when no run is active.

The alternative, a coordinator on the Mac dispatching with `worker-start --on <server>`, would
leave the host's agents at the default scope. Orca documents `--on` for paired Remote Orca
Servers; whether it also targets the managed server of an SSH host was not verifiable without a
live Orca, so v1 does not depend on it (see "Future").

## Running a feature

The full sequence, with the Users Management example: [examples/users-management/README.md](../examples/users-management/README.md).

1. **Specify**: the `solution-architect` writes `spec/requirements.md`, `architecture.md`,
   `api-contract.md`, `test-plan.md` and `plan.yaml` in the feature folder.
2. **Approve and pin**: a person reads them and runs
   `tte-harness spec lock <feature>/spec --approved-by "<name>"`. The lock records a SHA-256 per
   file and one digest; nothing after this point accepts another version.
3. **Prepare**: `tte-harness plan <feature>/plan.yaml` validates the DAG, refuses a spec that
   changed since its lock, copies the spec read-only into the run folder and renders one brief per
   task. It prints the parallel waves.
4. **Create the DAG in Orca**: `tte-harness orca commands --run-dir <run>` shows the calls;
   `tte-harness orca create --run-dir <run>` makes them: one Run, one Task per plan task with its
   brief as the spec and `--deps` as Orca ids, and a decision gate on every task with `approval:`.
5. **Coordinate**: launch the coordinator with
   [adapters/orca/coordinator-prompt.md](../adapters/orca/coordinator-prompt.md). It starts a
   worker per ready Task (`orca orchestration worker-start --task ... --worktree new-top-level
   --repo ... --agent claude|codex`), ends its turn, and is woken by Orca for every `worker_done`,
   `question` or escalation.
6. **Prove**: each worker runs `tte-harness evidence run` on its committed branch; the coordinator
   runs `tte-harness evidence check` before starting dependents; reviewers record verdicts with
   `tte-harness evidence review` from a clean checkout; integration records pull requests and CI
   with `tte-harness evidence pr`.
7. **Report and stop**: the coordinator writes the delivery report; a person merges.

## Task lifecycle and Orca states

Orca 1.4.256 has six task statuses (`orca orchestration task-update --help`): `pending`, `ready`,
`dispatched`, `completed`, `failed`, `blocked`. A `worker_done` settles a Task by itself, so a
"validating" or "in review" status inside Orca would race the worker. The harness derives those
states instead (`tte-harness status`, `config/harness.yaml` `states`):

| Harness state | Orca status | Observed when |
|---|---|---|
| PENDING | `pending` | dependencies not completed |
| READY | `ready` | `task-list --ready` lists it |
| RUNNING | `dispatched` | a worker holds it |
| VALIDATING | `completed` | the worker reported done, but a development gate fails `evidence check` |
| REVIEW | `completed` | development gates pass; its `review_by` task or a review gate is not done |
| COMPLETED | `completed` | review task completed and every non-human gate passes |
| BLOCKED | `blocked` | waiting on something outside the DAG |
| NEEDS_APPROVAL | `blocked` | the task has an `approval:` gate pending a person |
| FAILED | `failed` | the worker reported failure or the coordinator failed it on evidence |
| CANCELLED | `failed` + result `cancelled` | Orca's documented way to cancel: stop the worker, then `task-update --status failed --result cancelled` |

Because Orca marks a Task completed when its worker says so, the coordinator is the gate: Orca
never starts a worker on its own ("a Run ... never schedules or places workers"), so a dependent
starts only when the coordinator has seen its dependencies' evidence pass.

## Contracts and approvals

- The approved contract is part of the locked spec. A task that implements it carries
  `contract_change: approved`; every other task fails `no-contract-change` if its branch touches
  the repository's `contract_paths`.
- A worker that finds the contract wrong stops and asks (`orca orchestration ask`). The
  coordinator opens a decision gate; the architect revises the contract; a person approves; the
  spec is locked again with a new digest; affected tasks restart from new briefs. Briefs carry the
  digest, so work against the old version cannot pass `spec-pinned`.
- Merging is a person's act in GitHub. `human-merge-approval` is a `human` gate: `evidence check`
  lists it and never marks it passed.

## Failure handling

- `worker-start` failed: do not rerun it blindly; read `failedStage` and follow Orca's
  `recovery-and-cleanup` reference (`orca skills get orchestration --reference recovery-and-cleanup`).
- `tte-harness orca create` stopped part way: `orca-map.json` lists exactly what exists; inspect
  the Run (`orca orchestration run-show`) before doing anything by hand. The command refuses to run
  twice.
- A worker went silent: silence is not proof of exit (Orca's rule). Inspect with
  `orca orchestration worker-show`; stop only on a person's decision.

## Verified, simulated, pending

| Item | State |
|---|---|
| CLI resolution, command construction, receipt parsing, lifecycle mapping | verified by tests against a fake CLI that reproduces 1.4.256's `--json --full` receipts |
| `orca skills get`, `skills list`, `status`, the command schema | verified live on the Mac (runtime not running) |
| Run/Task/gate creation against a live Orca | pending: needs Orca open with orchestration enabled |
| SSH host with the SSM `ProxyCommand`, repo registration, worktree base path | pending: the devbox was unreachable from the build session (expired AWS SSO token) |
| `--on` to an SSH host's managed server | unverified; not used |

## Future

- A coordinator on the Mac dispatching to the devbox with `--on`, if Orca confirms it, so the host
  can stay at the default SSH scope.
- `tte-harness status --watch` fed by Orca events instead of on demand, if Orca exposes them.
- Per-task agent arguments (for example a read-only permission mode for reviewer workers) once
  `worker-start` accepts them.
