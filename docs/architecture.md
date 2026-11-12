# Architecture

`tte-agent-harness` is the one place where the team's agent roles, skills, workflows, templates
and quality gates are written down, versioned, validated and installed. It runs nothing by itself:
Orca runs the agents, the product repositories hold the code and their own rules, and the harness
connects the two with approved plans and recorded evidence.

## Responsibilities, one owner each

| Concern | Question it answers | Lives in | Owner |
|---|---|---|---|
| Agent definitions | who performs a task | `agents/<role>.md` | harness |
| Skills | how to perform an activity | `skills/<name>/SKILL.md` (+ `references/`) | harness |
| Workflows | in what order | `workflows/<name>/workflow.yaml` + `README.md` | harness |
| Quality gates | what proves a step is done | `config/quality-gates.yaml` | harness |
| Repository context | which constraints apply in a repository | each repository's `AGENTS.md`, `CLAUDE.md`, `.claude/project.json` | the product repository |
| Feature specification | what must be delivered | the feature folder: `spec/` + `plan.yaml` | the feature's owning repository |
| Orchestration | who runs when, where, after what | Orca Run, Tasks, gates, worktrees | Orca |
| Delivery mechanics | ticket, branch, plan, PR | tte-workflows (`/req`, `/plan-ticket`, `/make-pr`, ...) | tte-workflows |

The harness never copies a repository's rules into itself: a brief points the worker at the
repository's files, and `evidence run` reads the repository's validation sequence at run time.

## Components

```
tte-agent-harness/
├── agents/            8 canonical roles: frontmatter (name, description, access, skills, model,
│                      codex) + five required sections
├── skills/            13 portable Agent Skills (name/description/metadata only), shared by
│                      Claude Code and Codex
├── workflows/         4 stage graphs: feature-development, bug-fixing, code-review,
│                      release-validation
├── templates/         spec documents, the task brief, the delivery report, plan.yaml
├── config/            harness.yaml (access levels, lifecycle states, reserved names, external
│                      skills), quality-gates.yaml, repositories.example.yaml
├── adapters/          claude-code (permissions + format notes), codex (format notes, config
│                      example), orca (bridge notes, coordinator prompt)
├── tte_harness/       the CLI (Python 3.10+, PyYAML): validate, install, uninstall, doctor,
│                      repos, spec, plan, orca, status, evidence
├── bin/tte-harness    launcher that picks an interpreter with PyYAML
├── scripts/           install.sh, uninstall.sh, validate.sh, doctor.sh
├── tests/             unittest suite, no network, no live agents
└── examples/          users-management: a full spec, plan, lock and a lifecycle simulation
```

## One definition, two providers

```
agents/code-reviewer.md ──render──▶ ~/.claude/agents/code-reviewer.md     (Claude Code subagent)
                        └─render──▶ ~/.codex/agents/code-reviewer.toml    (Codex custom agent)
skills/api-design/      ──copy────▶ ~/.claude/skills/api-design/          (Claude Code)
                        └─copy────▶ ~/.agents/skills/api-design/          (Codex)
```

Skills are copied byte for byte: the Agent Skills format is shared, and the validator allows only
its portable frontmatter fields (`name`, `description`, `metadata`, and the other spec fields), so
no Claude-only key reaches Codex. Agents differ per provider, so they are rendered: Claude Code
gets `tools`/`disallowedTools` from the role's access level and `skills` to preload; Codex gets
`developer_instructions` and no sandbox keys, which it ignores in agent files.

## A feature, end to end

```
requirements ─▶ architecture + API contract ─▶ plan.yaml ─▶ person approves ─▶ spec lock (digest)
                                                                                    │
            tte-harness plan: validate DAG, check lock, read-only spec copy, briefs ◀┘
                                                                                    │
            tte-harness orca create: Run + Tasks (--deps) + decision gates in Orca ◀┘
                                                                                    │
  coordinator (Orca orchestration skill) starts workers on ready Tasks ◀────────────┘
     │            ▲
     ▼            │ worker_done / ask
  worker in its own worktree: implement, commit, `evidence run` ──▶ run folder evidence
     │
  coordinator: `evidence check` ─▶ PASS: start dependents │ FAIL: send back or fail
     │
  reviewer (`evidence review`) ─▶ integration (`evidence pr`) ─▶ delivery report ─▶ person merges
```

Details: [orchestration.md](orchestration.md). Repositories and specs:
[repository-integration.md](repository-integration.md). Rules: [security.md](security.md).

## Decisions

- **Orca, not a custom runtime.** Runs, Tasks, dependencies, workers, mail and gates are Orca's.
  The harness adds only what Orca does not hold: the approved plan, the briefs and the evidence.
- **Evidence over reports.** Orca completes a Task when its worker says so; the coordinator starts
  dependents only after `tte-harness evidence check` passes, and the lifecycle states VALIDATING
  and REVIEW are derived from evidence rather than self-reported.
- **Copies with a manifest, not symlinks.** Installed files are pinned to the harness commit that
  installed them; the manifest records each file's hash so updates, conflicts and uninstall touch
  only what the harness owns. The CLI wrapper is the exception: it runs the checkout.
- **Repositories own their commands.** Validation commands come from each repository's committed
  `.claude/project.json` (the tte-workflows convention), never from the harness.
- **Specs live with the feature, not in a new repository.** A feature folder sits in the
  repository that owns the change (or in this repository's `examples/`); the lock digest, not the
  location, is what workers pin.
- **Renamed review skills.** `code-review` and `security-review` are bundled Claude Code skills;
  the harness's are `tte-code-review` and `tte-security-review`, and the validator rejects any
  reserved name.
- **No license chosen.** The repository is public but carries no LICENSE file until the owners
  choose one, so all rights are reserved.
