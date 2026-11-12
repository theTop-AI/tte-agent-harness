# Codex adapter

How the canonical definitions become Codex CLI's native configuration. Verified against
learn.chatgpt.com/docs (build-skills, subagents, config reference) and the openai/codex source,
2026-11-12. Codex is not installed on the machine this was built on, so the installed files are
checked by parsing (TOML, frontmatter), not by a live Codex session yet.

## What `scripts/install.sh` writes

| Source | Installed as | Codex reads it as |
|---|---|---|
| `skills/<name>/` | `~/.agents/skills/<name>/` | a user skill, `$name` or chosen by its description |
| `agents/<name>.md` | `${CODEX_HOME:-~/.codex}/agents/<name>.toml` (rendered) | a custom agent (`spawn_agent`, `/subagents`) |

`~/.agents/skills` is Codex's current user-skill folder; `~/.codex/skills` still loads but is
deprecated. Codex does not merge two skills of the same name, it lists both, so the harness
installs each skill into exactly one Codex root. tte-workflows and `orca skills install` use the
same folder; `config/harness.yaml` reserves their names so nothing collides.

## Rendering a role

```toml
# Installed by tte-agent-harness from agents/code-reviewer.md at <rev>. ...
name = "code-reviewer"
description = "..."
model_reasoning_effort = "high"
developer_instructions = '''
Access: read-only - Reads code and runs read-only commands; never edits files.
Skills for this role (invoke them by name): $tte-code-review, $tte-security-review, ...
...the role text...
'''
```

No `sandbox_mode` or `approval_policy` is written: Codex ignores both in an agent file, and a
custom agent inherits its parent session's sandbox. A role's read-only rule therefore reaches Codex
as an instruction, and is enforced afterwards by the evidence gates (`tte-harness evidence review`
refuses a reviewer's dirty worktree).

## The session settings least privilege needs

Set these in `~/.codex/config.toml` on the host that runs Codex workers. The harness never edits
that file; [config.example.toml](config.example.toml) is the reviewed starting point.

- `sandbox_mode = "workspace-write"`: a worker writes only inside its worktree (plus `/tmp`).
- `approval_policy = "on-request"`: anything outside the sandbox asks a person.
- `[sandbox_workspace_write] network_access`: off by default. Repository validation that downloads
  dependencies (`pnpm install`, Playwright browsers, `uv sync`) needs it on; that is a deliberate,
  documented trade-off, not a default.
- Codex keeps `.git`, `.agents`, `.codex` and `.aws` read-only inside writable roots.

## Hooks

tte-workflows writes Codex's `hooks.json` (its delivery gate). The harness does not touch it.
