# tte-agent-harness — guide for agents working on this repository

Codex reads this file; Claude Code reads it through `CLAUDE.md`, which imports it.

This repository holds the team's shared agent roles, skills, workflows, templates, quality gates
and the `tte-harness` CLI that validates and installs them. It is never product code, and it never
writes into a product repository. Overview: [README.md](README.md); design:
[docs/architecture.md](docs/architecture.md).

## How to work here

- **Verify before you write.** Claude Code, Codex and Orca formats change; check the current docs
  or the installed CLI (`orca skills get orchestration`, `orca agent-context`) before adding or
  changing a field, a path or a flag, and cite where it came from. Never invent a command.
- **Run the checks** before every commit: `scripts/validate.sh` (structural validation, then the
  test suite). CI runs the same plus the example simulation and an install/uninstall round trip.
- **Every rule has a test that makes it fire.** A new validation rule, gate or installer behaviour
  comes with a test in `tests/` that fails without it.
- **Code**: Python 3.10+, standard library plus PyYAML only; shell scripts bash 3.2 compatible
  (macOS `/bin/bash`). No new dependency without a reason written in the pull request.
- **Content**: skills stay generic and point at a repository's own files instead of copying them;
  roles keep the five sections; workflows keep a README a person can follow. Docs are in English.
- **Security files** (`adapters/claude-code/permissions.json`, `config/harness.yaml`,
  `config/quality-gates.yaml`, `docs/security.md`) are changed only on a person's explicit request,
  in a pull request of their own. An execution worker never edits them.
- A change that alters what gets installed bumps the affected skill's `metadata.version` and is
  described in the pull request.

## Commits and pull requests

The tte conventions (tte-workflows CONTRIBUTING): Conventional Commit header
`type(scope): what changed` (≤ 100 characters; scopes such as `agents`, `skills`, `workflows`,
`installer`, `orca`, `docs`, `ci`), the why in the body, footers `Docs-Updated: <path>` or
`Docs-Updated: none — <reason>` and `Refs: TTE-123`. Branch `type/TTE-123-what-it-is`.
Never commit or push without an explicit request; never merge.
