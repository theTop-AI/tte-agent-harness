# Repository integration

How a product repository joins the harness, what stays inside the repository, where feature specs
live, how a spec version reaches every worker, and how the harness sits beside tte-workflows.

The rule underneath all of it: **the harness never writes into a product repository.** It reads
a repository's own files, and workers change a repository only through the worktree Orca gave
them, under that repository's own rules.

## Onboarding a repository

Four steps, none of which touch the repository itself.

### 1. Add it to the repositories file

`config/repositories.example.yaml` is the committed shape; each host keeps its paths in
`config/repositories.yaml` (git-ignored). Add an entry to both:

```yaml
repositories:
  tte-billing:                           # the key plans use as `repo:`
    github: theTop-AI/tte-billing        # owner/name
    path: /home/ubuntu/projects/tte-billing   # absolute; per host in repositories.yaml
    kind: backend                        # frontend | backend | infrastructure | experimental | ...
    summary: One line on what it is.
    context: [AGENTS.md, README.md]      # what every brief tells a worker to read first
    contract_paths:                      # files only an approved contract change may touch
      - openapi.json
    roles: [solution-architect, backend-developer, backend-qa, code-reviewer, integration-engineer]
```

| Field | Meaning | Checked by |
|---|---|---|
| `github` | `owner/name`; doctor checks your permission on it | `validate`, `doctor` |
| `path` | the shared checkout on this host; workers never edit it, Orca makes worktrees from it | `doctor` |
| `kind` | free text for people and the architect | `validate` (required) |
| `context` | files a brief lists under "Where you work" | — |
| `contract_paths` | a path ending in `/` is a folder prefix, anything else an exact file; a change to one fails `no-contract-change` unless the task carries `contract_change: approved` | `evidence run`, `evidence check` |
| `roles` | the agents a plan may assign here; a plan task with another role is rejected | `validate`, `plan` |

Leave a role out to keep it out: `tte-infra` lists no developer role in v1, so no plan can send a
worker to change infrastructure.

### 2. Commit a validation sequence in the repository

The harness has **no copy** of any repository's lint, typecheck or test commands. They live in the
repository's own committed `.claude/project.json`, the tte-workflows convention, so CI,
tte-workflows' `/implement` and the harness all run the same list:

```json
{
  "name": "tte-billing",
  "baseBranch": "main",
  "validate": [
    { "name": "lint", "run": "make lint" },
    { "name": "tests", "run": "make test", "timeout": 1800 },
    { "name": "contract", "run": "make openapi-check", "when": ["src/api/*", "openapi.json"] }
  ]
}
```

`tte-harness evidence run` reads that file from the worker's worktree at run time and runs each
step with `bash -c` from the repository root. `when` (a glob or list; `*` also crosses `/`) limits a
step to branches that change a matching path against the merge-base with `baseBranch`; `timeout`
is in seconds (default 1800). A repository without the file cannot pass `repo-validate`: adding it
is a change to that repository, made through its own pull request, never by the harness.

`tte-harness repos` prints every repository's live sequence from the checkouts on this host.

### 3. Register it in Orca on the host

In Orca, on the devbox's SSH workspace, add the checkout as a project (the repository's existing
folder at `path`). Orca then creates task worktrees from it under its worktree root
(`/home/ubuntu/orca/workspaces/` on tte-devbox-vlad). Details and the settings orchestration needs:
[orchestration.md](orchestration.md).

### 4. Check

```bash
bin/tte-harness validate     # the entry is well-formed, its roles exist
scripts/doctor.sh            # checkout, worktrees, committed validation sequence, your permission
```

## The repository keeps its own instructions

A product repository's `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, ADRs and living specs stay in
that repository and are its authority. The harness's agents and skills are written to be generic:
they tell a worker to read the repository's files first and say that the repository wins where it
is stricter. Branch names, commit headers, `Docs-Updated:` and `Refs:` footers, and when to push
come from the repository and tte-workflows, never from a harness file. The harness installs into
the user's tool configuration (`~/.claude`, `~/.agents`, `~/.codex`), so nothing it ships is
committed into a product repository and no two repositories carry diverging copies of it.

## Where feature specs live

| What | Where | Why |
|---|---|---|
| A cross-repository feature (requirements, architecture, API contract, test plan, `plan.yaml`) | the owning product repository, `docs/features/<feature-id>/` (the repository that owns the contract, usually the backend) | versioned with the code that implements it; reviewed in a pull request like code |
| The behaviour a capability has today | `docs/specs/<capability>.md` in each product repository: tte-workflows' living specs, OpenSpec-shaped, edited in the same pull request as the behaviour | the merge is the archive; tte-workflows' `specs` lint holds the shape |
| The harness's own example | `examples/users-management/` in this repository | it must not touch product repositories |

There is no `tte-specs` repository, and none is needed: a feature's spec belongs beside its code,
and the living specs already have a home (tte-workflows decision, 2026-10-29). A feature folder
follows `templates/` (requirements, architecture, api-contract, test-plan, plan.yaml).

## How a spec version is pinned and distributed

Parallel workers in different repositories never share a session, a context or a file system view
of each other's changes. What they share is one approved spec version, carried three ways:

1. **Lock.** Once a person approves the spec,
   `tte-harness spec lock docs/features/<id>/spec --approved-by "<name>"` writes `spec.lock.json`:
   the SHA-256 of every spec file, one digest over all of them, who approved it, when, and the
   commit it was locked at. Committing the lock in the same pull request makes the approval part
   of history.
2. **Refusal.** `tte-harness plan` verifies the lock first and refuses a spec that changed since:
   an edited contract cannot reach a worker unless someone approves and locks it again.
3. **Distribution.** `plan` writes the run folder: a read-only copy of the locked spec
   (`<run>/spec/`), and one brief per task (`<run>/briefs/<task>.md`) that names the digest and
   quotes, verbatim, the spec sections the task lists as `inputs` (`api-contract.md#endpoint-list-users`).
   Orca delivers the brief as the worker's task (`task-create --spec-file`), so the contract
   travels inside the assignment, not as a path the worker has to find.

Every evidence record carries the digest it was produced against, and the `spec-pinned` gate fails
evidence recorded against any other version. A contract change mid-flight is therefore always an
explicit step: the worker stops and asks (`orca orchestration ask`), the architect revises and bumps
the contract version, a person approves, the lock changes, `plan` writes new briefs, and the
affected tasks restart from them.

## Relationship with tte-workflows

[tte-workflows](https://github.com/theTop-AI/tte-workflows) is the team's delivery tooling, and it
stays the authority for everything it covers. The harness does not replace, copy or migrate any of
it.

| tte-workflows owns | The harness adds |
|---|---|
| The ticket-anchored delivery run of one ticket in one repository: `/req`, `/plan-ticket`, `/review-plan`, `/publish-plan`, `/implement`, `/scope-check`, `/make-pr` | Roles (agent definitions) and engineering skills shared by Claude Code and Codex |
| Jira: tickets, branches named after keys, plan comments, state moves up to In Review | Cross-repository planning: a feature DAG over several repositories, run as one Orca Run |
| Each repository's validation sequence convention (`.claude/project.json`) | Evidence recorded by command against that same sequence, and gates decided from it |
| Living specs (`docs/specs/`) and their lint | Spec locking and distribution of a feature's approved spec to parallel workers |
| `no_apply_guard.py` (no `terraform apply` from agents) | An installer, a doctor and a validator for the shared definitions, plus opt-in Claude Code deny rules |

How they meet:

- **Separate installs, no shared files.** tte-workflows' `setup.sh` installs its skills into
  `~/.claude/skills` and `~/.agents/skills`; the harness installs into the same folders under
  different names and owns only what its manifest lists. The names tte-workflows ships (`req`,
  `plan-ticket`, `implement`, `make-pr`, `review-plan`, `publish-plan`, `scope-check`, `memory-run`)
  are reserved in `config/harness.yaml`, so `validate` rejects a harness skill that would collide
  with one.
- **A worker may run tte-workflows inside its repository.** A harness task is one repository's
  share of a feature; a worker can carry it with `/plan-ticket TTE-123` → `/implement` →
  `/make-pr` on the ticket's branch, which gives the task tte-workflows' own plan, validation and
  scope audit. The decision a delivery run asks of "the person" then travels to the coordinator
  through `orca orchestration ask`, and on to a person.
- **Conflicts.** Where tte-workflows and the harness disagree on a Jira, branch or pull-request
  rule, tte-workflows wins, and the harness file is the one to fix.
