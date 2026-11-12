"""Render one canonical role (agents/<name>.md) into each provider's native agent format.

Claude Code: ~/.claude/agents/<name>.md, YAML frontmatter (name, description, tools,
disallowedTools, model, skills) and the role text as the system prompt.

Codex: ~/.codex/agents/<name>.toml with name, description and developer_instructions
(learn.chatgpt.com/docs/agent-configuration/subagents, 2026-11). Codex ignores sandbox_mode and
approval_policy in an agent file - a custom agent inherits its parent's sandbox - so they are not
written: a role's read-only rule reaches Codex as instructions and is enforced by evidence checks
(`evidence review` refuses a dirty worktree), not by the file.
"""

from __future__ import annotations

from typing import Any

import yaml

from .model import Agent, Harness

GENERATED = ("Installed by tte-agent-harness from agents/{name}.md at {rev}. "
             "Edit the source in the harness and reinstall; local edits are reported as conflicts.")


def claude_agent(h: Harness, agent: Agent, rev: str) -> str:
    access = h.access_levels[agent.access]
    meta: dict[str, Any] = {
        "name": agent.name,
        "description": " ".join(agent.description.split()),
        "tools": ", ".join(access.get("tools", [])),
    }
    if access.get("disallowed_tools"):
        meta["disallowedTools"] = ", ".join(access["disallowed_tools"])
    meta["model"] = str(agent.meta.get("model") or "inherit")
    if agent.skills:
        meta["skills"] = list(agent.skills)
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000).strip()
    note = GENERATED.format(name=agent.name, rev=rev)
    return f"---\n{front}\n---\n<!-- {note} -->\n\n{agent.body.strip()}\n"


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_multiline(value: str) -> str:
    if "'''" not in value:
        return "'''\n" + value + "'''"
    escaped = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return '"""\n' + escaped + '"""'


def codex_agent(h: Harness, agent: Agent, rev: str) -> str:
    access = h.access_levels[agent.access]
    skills = ", ".join(f"${s}" for s in agent.skills)
    preamble = (
        f"Access: {agent.access} - {access.get('description', '').strip()}\n"
        f"Skills for this role (invoke them by name): {skills}\n\n"
    )
    instructions = preamble + agent.body.strip() + "\n"
    lines = [
        f"# {GENERATED.format(name=agent.name, rev=rev)}",
        f"name = {_toml_string(agent.name)}",
        f"description = {_toml_string(' '.join(agent.description.split()))}",
    ]
    codex = agent.meta.get("codex") or {}
    if codex.get("reasoning_effort"):
        lines.append(f"model_reasoning_effort = {_toml_string(str(codex['reasoning_effort']))}")
    lines.append(f"developer_instructions = {_toml_multiline(instructions)}")
    return "\n".join(lines) + "\n"
