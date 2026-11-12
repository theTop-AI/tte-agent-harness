# tte-agent-harness

The team's AI agent harness: one version-controlled source for agent roles, skills, workflows,
templates, quality gates and repository integration, installed for **Claude Code** (primary) and
**Codex CLI** (secondary), orchestrated by **Orca IDE**, with agents and Git worktrees running on
the AWS devbox.

It runs no agents itself. Orca runs them; the product repositories (`tte-frontend`, `tte-engine`,
`tte-infra`, `tte-lab`) keep their code and their own rules; the harness connects the two with
approved, pinned specifications and evidence that a task is really done.

```
spec (approved, locked) ─▶ tte-harness plan ─▶ Orca Run + Tasks ─▶ workers in worktrees
                                                      ▲                   │
                         coordinator ◀── evidence check ◀── evidence run ◀┘
```

- [Architecture](docs/architecture.md): what lives where, and why.
- [Getting started](docs/getting-started.md): install on the devbox or a Mac.
- [Orchestration](docs/orchestration.md): Orca setup, activation, the task lifecycle.
- [Repository integration](docs/repository-integration.md): onboarding a repository, specs,
  tte-workflows.
- [Security](docs/security.md): every rule and where it is enforced.
- [Users Management example](examples/users-management/README.md): a full feature, simulated.

## What is in it

| Folder | Holds |
|---|---|
| [`agents/`](agents/) | 8 roles: solution-architect, coordinator, frontend-developer, backend-developer, frontend-qa, backend-qa, code-reviewer, integration-engineer |
| [`skills/`](skills/) | 13 portable Agent Skills (below) |
| [`workflows/`](workflows/) | feature-development, bug-fixing, code-review, release-validation |
| [`templates/`](templates/) | requirements, architecture, API contract, test plan, task brief, delivery report, plan.yaml |
| [`config/`](config/) | `harness.yaml` (access levels, lifecycle states, reserved names, external skills), `quality-gates.yaml`, `repositories.example.yaml` |
| [`adapters/`](adapters/) | [claude-code](adapters/claude-code/README.md), [codex](adapters/codex/README.md), [orca](adapters/orca/README.md) |
| [`tte_harness/`](tte_harness/), [`bin/`](bin/), [`scripts/`](scripts/) | the `tte-harness` CLI and its shell entry points |
| [`tests/`](tests/) | the test suite CI runs (no network, no live agents) |

### Roles

| Role | Does | Access | Skills |
|---|---|---|---|
| solution-architect | requirements, architecture, API contract, task graph; nothing built before approval | spec-write | requirements-analysis, solution-architecture, api-design, task-decomposition |
| coordinator | turns the approved plan into an Orca Run, starts workers, gates on evidence, reports | coordinate | feature-delivery, task-decomposition, integration-validation |
| frontend-developer | implements frontend tasks to the pinned contract | repo-write | react-development, api-design, frontend-testing |
| backend-developer | implements APIs, logic, migrations, tests | repo-write | python-development, api-design, backend-testing |
| frontend-qa | component, integration, E2E tests; test-first | repo-write | frontend-testing, react-development |
| backend-qa | API, contract, authorization, isolation tests | repo-write | backend-testing, python-development, api-design |
| code-reviewer | independent review; records verdicts from a clean checkout | read-only | tte-code-review, tte-security-review, skill-management |
| integration-engineer | integrates branches, validates FE + BE, opens PRs, never merges | repo-write | integration-validation, tte-code-review |

### Skills

| Planning | Development | Quality | Delivery |
|---|---|---|---|
| requirements-analysis, solution-architecture, api-design, task-decomposition | react-development, python-development | frontend-testing, backend-testing, tte-code-review, tte-security-review | feature-delivery, integration-validation, skill-management |

Each skill is a `SKILL.md` with `name`, `description` (when to use it) and `metadata`
(category, version) and six sections: when to use, inputs, procedure, outputs, validation,
escalation. Detail goes to `references/`. The review skills are `tte-`-prefixed because Claude Code
bundles `/code-review` and `/security-review`; the validator rejects any name another tool
installs into the same folder (including tte-workflows' and Orca's skills).

## Install

On the devbox (details, prerequisites and the macOS variant: [getting-started](docs/getting-started.md)):

```bash
aws sso login --profile tte-dev && ssh tte-devbox-vlad        # from the Mac
git clone https://github.com/theTop-AI/tte-agent-harness.git ~/projects/tte-agent-harness
cd ~/projects/tte-agent-harness && git checkout <tag-or-commit>
cp config/repositories.example.yaml config/repositories.yaml  # adjust paths if needed
scripts/install.sh --dry-run --ref <tag-or-commit>
scripts/install.sh --ref <tag-or-commit>
scripts/install.sh --with-orca-skills       # from a terminal Orca opened on the host
scripts/doctor.sh
```

It installs, for each provider it finds, without root and without touching anything it does not
own:

| | Claude Code | Codex |
|---|---|---|
| skills | `~/.claude/skills/<name>/` | `~/.agents/skills/<name>/` |
| roles | `~/.claude/agents/<name>.md` (subagent) | `~/.codex/agents/<name>.toml` (custom agent) |

plus `~/.local/bin/tte-harness` and a manifest in `~/.local/state/tte-agent-harness/`. A dry run
writes nothing; a second run changes nothing; a file you edited is a conflict and is kept;
`scripts/uninstall.sh` removes only unmodified harness files. `--with-permissions` adds the
[Claude Code deny/ask rules](adapters/claude-code/permissions.json) to `settings.json` (additive,
reversible).

## Run a feature

1. The `solution-architect` writes `spec/` and `plan.yaml` from [templates](templates/).
2. A person approves; `tte-harness spec lock <feature>/spec --approved-by "<name>"` pins it.
3. `tte-harness plan <feature>/plan.yaml` validates the DAG and writes one brief per task.
4. `tte-harness orca create --run-dir <run>` creates the Orca Run, Tasks, dependencies and gates.
5. Start the coordinator with [adapters/orca/coordinator-prompt.md](adapters/orca/coordinator-prompt.md);
   it starts workers through Orca and checks `tte-harness evidence check` before every dependent.
6. Workers prove their work with `tte-harness evidence run`; reviewers with `evidence review`;
   integration with `evidence pr`. `tte-harness status` shows the lifecycle.
7. The coordinator writes the delivery report; a person merges.

Try the whole lifecycle with nothing real touched: `examples/users-management/simulate.sh`.

## Command reference

| Command | Does |
|---|---|
| `tte-harness validate [--warnings]` | every structural rule: frontmatter, sections, references, DAGs, gates, repositories, templates, the example, links, credentials |
| `tte-harness install [--dry-run] [--providers ...] [--ref REV] [--force] [--with-permissions] [--with-orca-skills]` | install or update for this user |
| `tte-harness uninstall [--dry-run]` | remove what install wrote, keep edited files |
| `tte-harness doctor [--json] [--offline]` | check tools, install, Orca, repositories; prints a fix for every failure |
| `tte-harness repos` | repositories and their live validation sequence |
| `tte-harness spec lock DIR --approved-by NAME` / `spec verify DIR` | pin an approved spec / detect changes since |
| `tte-harness plan PLAN [--run-dir DIR] [--check]` | validate a plan; prepare its run folder and briefs |
| `tte-harness orca commands\|create --run-dir DIR` | print / make the Orca calls for the run |
| `tte-harness status --run-dir DIR [--orca-json FILE]` | lifecycle state of every task |
| `tte-harness evidence run\|review\|pr\|check --run-dir DIR --task ID` | record and decide evidence |

Exit codes: 0 ok, 1 a check failed, 2 usage or configuration error, 3 installed with conflicts.

## Extending

**A repository**: add an entry to `config/repositories.example.yaml` (and the host's
`repositories.yaml`) with `github`, `path`, `kind`, `context`, `contract_paths`, `roles`; make
sure the repository commits a `.claude/project.json` with its `validate` list; register it in Orca
on the host. Full steps: [repository-integration](docs/repository-integration.md).

**A role**: `agents/<name>.md` with `name`, `description`, `access` (a level in
`config/harness.yaml`), `skills`, optional `model` and `codex.reasoning_effort`, and the sections
Responsibilities, Inputs, Outputs, Boundaries, Escalate when. Add it to the `roles` of every
repository it may work in. `tte-harness validate` renders it for both providers to check it.

**A skill**: `skills/<name>/SKILL.md` with only portable frontmatter (`name` = folder,
`description` containing "Use when", `metadata.category`, `metadata.version`), the six sections,
under 500 lines, every extra file linked from SKILL.md. List it in the roles that use it.
External skills: follow the `skill-management` skill; nothing is downloaded automatically.

**A workflow**: `workflows/<name>/workflow.yaml` (stages with `id`, `title`, `role`, `skills`,
`depends_on`, `gates`, optional `approval` and `per_repository`) and a `README.md` a person can
follow.

**A validation rule**: a quality gate goes in `config/quality-gates.yaml` (`stage`, `kind`:
evidence | review | human, `description`). An `evidence` gate also needs its rule in
`tte_harness/evidence.py` `check_task`; a development-stage gate must be `evidence`. A structural
rule for the harness itself goes in `tte_harness/validate.py`. Every rule gets a test in `tests/`
that makes it fire.

## Updating and versioning

The harness is installed from a commit or tag, never a moving branch: `--ref` refuses a checkout
that is elsewhere, the manifest records the commit, and `doctor` warns when the checkout moved
past what is installed. To update: `git fetch --tags && git checkout <tag> &&
scripts/install.sh --ref <tag>`. Skills carry `metadata.version` (semver); bump it with any
change to a skill's behaviour. Tags follow semver for the harness as a whole.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ssh tte-devbox-vlad`: `Token has expired` | the AWS SSO session expired: `aws sso login --profile tte-dev` |
| `tte-harness needs Python 3.10+ with PyYAML` | `sudo apt-get install -y python3-yaml` (Ubuntu) or `brew install uv` (macOS) |
| install exits 3 | a file you edited, or someone else's skill of the same name, was left alone; restore it or rerun with `--force` (backs it up) |
| `uncommitted changes ... pass --allow-dirty` | install from a commit: commit or stash, or check out the tag |
| skills not visible in a session | start a new session; under an Orca managed Claude account, install from that pane (doctor warns) |
| `orca`: GNOME screen reader / not found on Linux | run from a terminal Orca opened on the host; doctor shows which CLI it resolved |
| `orca orchestration` FAIL in doctor | Settings → Experimental → orchestration; on the coordinator's SSH host, the control permission ([orchestration](docs/orchestration.md#activating-orca-orchestration)) |
| `evidence check`: `no committed .claude/project.json` | the repository has no validation sequence: add one in that repository (its own PR) |
| `spec ... changed since it was approved` | someone edited the spec after the lock: re-approve and `spec lock` again, then `plan` again |

## Relationship with tte-workflows

[tte-workflows](https://github.com/theTop-AI/tte-workflows) owns the ticket-to-pull-request
delivery run (`/req`, `/plan-ticket`, `/implement`, `/scope-check`, `/make-pr`), Jira, living
specs in `docs/specs/`, and the `no_apply_guard` hook. It stays the authority for branch, commit,
ticket and PR conventions; workers follow it inside each repository. The harness adds what spans
repositories and sessions: roles, engineering skills, Orca orchestration, pinned specs and
evidence. The two install side by side into the same folders without collisions (reserved
names), and neither modifies the other. Nothing was migrated or deleted.

## Security

Least privilege by default: one worktree per worker, no credential reads, no merge, no force-push,
no deploy, no `terraform apply`, no automatic third-party skills, no destructive cleanup without a
person, and the harness's own rules guarded by `ask` rules and CODEOWNERS. Each rule and its
limits: [docs/security.md](docs/security.md).

## License

Published by theTop-AI without a license. The code is readable, but no license has been chosen,
so all rights are reserved: no permission to use, copy, modify or distribute it is granted until
the owners choose a license.
