# Claude Code adapter

How the canonical definitions become Claude Code's native configuration. Verified against
code.claude.com/docs (sub-agents, skills, permissions) and Claude Code 2.1.322, 2026-11-12.

## What `scripts/install.sh` writes

| Source | Installed as | Claude Code reads it as |
|---|---|---|
| `skills/<name>/` (whole folder) | `~/.claude/skills/<name>/` | a personal skill, `/name` or chosen by its description |
| `agents/<name>.md` | `~/.claude/agents/<name>.md` (rendered) | a user-level subagent |
| `adapters/claude-code/permissions.json` | merged into `~/.claude/settings.json`, only with `--with-permissions` | `permissions.deny` / `permissions.ask` rules |

`~/.claude` is `$CLAUDE_CONFIG_DIR` when that is set. Orca sets it per pane when a managed Claude
account is selected (`ORCA_CLAUDE_INJECTED_CONFIG_DIR`); `tte-harness doctor` warns about that case,
because files in `~/.claude` are then invisible to that account.

## Rendering a role

The canonical frontmatter (`name`, `description`, `access`, `skills`, `model`, `codex`) is turned
into the subagent frontmatter Claude Code documents:

- `tools` / `disallowedTools` come from the role's `access` level in `config/harness.yaml`; a
  `read-only` reviewer gets `Read, Grep, Glob, Bash` and has `Edit, Write, NotebookEdit` removed.
- `skills` preloads each listed skill's full text into the subagent at start-up.
- `model` defaults to `inherit`.
- A comment line names the harness revision; edit the source, never the installed file (the
  installer reports a local edit as a conflict and keeps it).

## Subagents are not Orca workers

A subagent runs inside one Claude Code session, shares its working directory and permission mode,
and returns a summary to its parent. An Orca worker is a separate top-level session Orca launches
in its own worktree. Orca 1.4.256's `worker-start` passes no per-task CLI flags, so a worker's
tool limits come from the host's Claude Code settings (the deny/ask rules above), not from a role
file; the role reaches the worker as text in its task brief. The installed subagents are for
delegation inside a session: a developer asking `code-reviewer` for a pre-review, a coordinator
asking `solution-architect` to restate a contract. See [docs/orchestration.md](../../docs/orchestration.md).

## Permissions

`permissions.json` holds two lists. `deny` blocks credential reads (`~/.aws`, `~/.ssh`, `.env`
files, CLI tokens) and irreversible actions (merging, force-pushing, pushing to `main`, deleting
repositories, `terraform apply`/`destroy`, `orca orchestration reset`). `ask` makes a person decide
everything else that is outward-facing or that widens what agents can do: any `aws` call, tags and
releases, installing skills or plugins, removing Orca worktrees, and edits to the harness's own
configuration. Rules are matched as command prefixes: a wrapper such as `bash -c "..."` can get
past them, which is why branch protection and the evidence gates exist too. Details and how to
widen access on purpose: [docs/security.md](../../docs/security.md).
