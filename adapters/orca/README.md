# Orca adapter

Orca IDE is the only orchestrator. It owns Runs, Tasks, workers, worktrees, mail and decision
gates; the harness owns the approved plan, the briefs and the evidence, and talks to Orca only
through its CLI. Facts below were read from Orca 1.4.256 (`orca agent-context`, the bundled
`orca skills get orchestration --full` guide, and the CLI handlers) and orca.dev/docs, 2026-11-12.

## What is wired, and how

| Harness piece | Orca capability it uses | Status |
|---|---|---|
| `tte-harness install --with-orca-skills` | `orca skills install --skill orca-cli --skill orchestration` (Orca's own installer, version-matched to the host's Orca) | wired; needs an Orca CLI on the host |
| `tte-harness orca commands` | prints `orchestration run-create`, `task-create --spec-file <brief> --deps <ids>`, `gate-create` in dependency order | verified offline |
| `tte-harness orca create` | runs those calls with `--json --full`, reads `result.run.id`, `result.task.id`, `result.gate.id`, writes `orca-map.json` after each call; `--from <handle>` when not run inside an Orca terminal | **verified live** (Orca 1.4.256, 2026-11-12: Run, 2 Tasks with dependency, 1 gate) |
| `tte-harness status` | `orchestration task-list --run <id> --json --full` (`result.tasks[].status`), mapped to the harness lifecycle | **verified live** (READY, and NEEDS_APPROVAL for the gated Task Orca set to `blocked`) |
| starting workers, mail, gates | the coordinator agent uses Orca's `orchestration` skill directly | Orca-native, nothing re-implemented |
| CLI resolution | `ORCA_CLI_COMMAND`, `orca-dev`, `orca-ide` on Linux (on `PATH`, in `$ORCA_CLI_BIN_DIR`, or in `~/.orca/cli/bin` where the managed server puts it), bare `orca` only inside an Orca terminal (`ORCA_TERMINAL_HANDLE`) — the rule of Orca's own skill stubs, because `/usr/bin/orca` on Linux is the GNOME screen reader | verified, on the devbox too |

The harness never polls Orca, never starts workers itself, and never calls `orchestration reset`
(it is in the deny list).

## Files

- [coordinator-prompt.md](coordinator-prompt.md): the prompt that starts the coordinator for one
  prepared run. Launch it in an Orca chat or with
  `orca agent launch --agent claude --prompt "$(cat <filled prompt>)" --json`.

## Activation

Step by step, with the exact settings and their security implications:
[docs/orchestration.md](../../docs/orchestration.md#activating-orca-orchestration).
In short: Settings → Experimental → orchestration on; Settings → SSH → add `tte-devbox-vlad`
from the OpenSSH config picker; on that host, Advanced Connection → *Allow this host's orca CLI to
control Orca* (only because the coordinator runs there; read the trade-off first); register the
repositories on the host; run `scripts/doctor.sh` from an Orca terminal on the host.
