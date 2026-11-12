# Example: Users management (tte-frontend + tte-engine)

A complete, illustrative feature that crosses two repositories: a Users screen in `tte-frontend`
backed by a new `GET /api/v1/users` in `tte-engine`. It shows the whole lifecycle the harness
supports, from analysis to merge approval, and `simulate.sh` runs every harness step of it against
throwaway repositories so you can watch it work without touching a product repository or Orca.

> Not a real ticket. The spec cites real files and conventions of both repositories as of
> 2026-11-12, but nothing was implemented, and the approval in `spec/spec.lock.json` is a
> placeholder ("example only - not a real approval").

| File | What it is |
|---|---|
| [spec/requirements.md](spec/requirements.md) | business context, FR/NFR, acceptance criteria, risks, Definition of Done |
| [spec/architecture.md](spec/architecture.md) | context read from both repositories, components, decisions, delivery shape |
| [spec/api-contract.md](spec/api-contract.md) | `users-api` 1.0.0: the one endpoint, its schemas, errors, paging |
| [spec/test-plan.md](spec/test-plan.md) | backend and frontend scenarios mapped to every AC, test-first order |
| `spec/spec.lock.json` | the pinned version: a digest of the four files above |
| [plan.yaml](plan.yaml) | the task DAG: seven tasks, three waves |
| [simulate.sh](simulate.sh) | the lifecycle end to end, nothing real touched |

## Run it

```bash
bin/tte-harness spec verify examples/users-management/spec        # the spec matches its lock
bin/tte-harness plan examples/users-management/plan.yaml --check  # the DAG is valid
examples/users-management/simulate.sh                              # the whole lifecycle, simulated
```

`simulate.sh` needs only git, bash and the harness launcher. It puts stub `orca` and `gh` commands
first on `PATH` that fail if called, uses its own git identity with no global config, and removes
its temporary folder on exit (`KEEP=1` keeps it).

## The lifecycle, step by step

| # | Step | Who | Where it happens | Command or file |
|---|---|---|---|---|
| 1 | Analyse the repositories | solution-architect | a Claude Code session (or Orca worker) with read access to both checkouts | skills `requirements-analysis`, `solution-architecture`; reads `src/contextbank/server/api/*`, `apps/web/src/features/*` |
| 2 | Requirements and architecture | solution-architect | the feature folder | `spec/requirements.md`, `spec/architecture.md` from `templates/` |
| 3 | Versioned API contract | solution-architect | the feature folder | skill `api-design` → `spec/api-contract.md` (`users-api` 1.0.0) |
| 4 | A person approves the spec | a person | — | `tte-harness spec lock <spec> --approved-by "<name>"` writes `spec.lock.json` |
| 5 | Dependency graph | solution-architect (skill `task-decomposition`), coordinator | the feature folder, then the run folder | `plan.yaml`; `tte-harness plan plan.yaml --run-dir <run>` prints the waves |
| 6 | Launch FE, BE, FE QA, BE QA in parallel | coordinator | Orca | `tte-harness orca create --run-dir <run>`, then per ready task `orca orchestration worker-start --task <id> ...` (docs/orchestration.md) |
| 7 | Each worker gets a brief and the contract | Orca → worker | the worker's prompt | `<run>/briefs/<task>.md`: role, spec digest, quoted spec sections, gates, evidence commands |
| 8 | Isolated worktree in the right repository | Orca | the SSH host's worktree root | one new worktree per task, created by `worker-start`, never the shared checkout |
| 9 | Code and tests per repository | developers and QA | their worktrees | commits; `tte-harness evidence run` and `evidence check` |
| 10 | FE + BE validated together | integration-engineer | integration worktree | skill `integration-validation`; frontend e2e against the real engine build |
| 11 | Independent review | code-reviewer | a clean checkout of each branch | skills `tte-code-review`, `tte-security-review`; `tte-harness evidence review` |
| 12 | Delivery report and PR links | coordinator | the run folder | `tte-harness status`, `tte-harness evidence pr`, `templates/delivery-report.md` |
| 13 | A person approves the merges | a person | Orca decision gate, then GitHub | the `integration` task's gate; `human-merge-approval` is never satisfied by an agent |

The plan puts review (11) before integration (10): each repository's branches are reviewed as
soon as both of its tasks finish, and integration starts from reviewed branches only. The pull
requests then get their own CI and human review on GitHub.

## Parallel execution plan

```text
wave 1 (parallel)  be-users-api      backend-developer   tte-engine    contract_change: approved
                   be-users-tests    backend-qa          tte-engine    test-first
                   fe-users-screen   frontend-developer  tte-frontend  against the mock engine
                   fe-users-tests    frontend-qa         tte-frontend  test-first
wave 2 (parallel)  review-engine     code-reviewer       tte-engine    after be-users-api, be-users-tests
                   review-frontend   code-reviewer       tte-frontend  after fe-users-screen, fe-users-tests
wave 3             integration       integration-engineer tte-frontend after both reviews; decision gate first
```

Why wave 1 can really run in parallel: the four tasks depend on the approved contract, not on each
other. The frontend builds against `@tte/mock-engine` answering the approved contract; the QA tasks
write tests that fail for the right reason ("route not found") until the implementation lands.
What cannot run in parallel is not pretended to: the frontend's pinned contract moves only in the
integration task, after the engine change exists.

## Gates per task

| Task | Gates |
|---|---|
| be-users-api, fe-users-screen | repo-validate, clean-commit, spec-pinned, no-contract-change, no-secrets, security-reviewed, review-pass |
| be-users-tests, fe-users-tests | repo-validate, clean-commit, spec-pinned, no-contract-change, no-secrets, tests-cover-criteria, review-pass |
| review-engine, review-frontend | none of their own: they record the review evidence of the tasks they review |
| integration | pr-created, ci-green, human-merge-approval |

`be-users-api` is the only task allowed to change a contract path (`openapi.json`), because it
carries `contract_change: approved`; the same change from `be-users-tests` fails
`no-contract-change` (step 6 of the simulation).

## Expected pull requests

| Repository | Branch | Title | Contains |
|---|---|---|---|
| tte-engine | `feat/TTE-<n>-users-api` | `feat(api): list the organization's panel members at /api/v1/users` | `server/api/users.py`, the query, regenerated `openapi.json`, unit and API tests B-1…B-10, `docs/specs/users.md` |
| tte-frontend | `feat/TTE-<n>-users-screen` | `feat(web): show the organization's panel members on a Users screen` | `features/users/`, `routes/_authed/_app/users.tsx`, mock-engine fixture, tests F-1…F-8, the pinned contract moved to the engine release, `docs/specs/users.md` |

Both bodies carry `Docs-Updated:` and `Refs: TTE-<n>` (tte-workflows conventions); the engine
pull request merges and releases first. No agent merges either.

## What is verified, simulated, pending activation, or future

| Category | What |
|---|---|
| **Verified executable** (simulate.sh runs it) | spec lock verification; plan validation and wave computation; brief rendering with the pinned spec quoted; the exact Orca command sequence (printed); `evidence run` executing a repository's committed `.claude/project.json` sequence; gate decisions (dirty tree, contract change, missing review, approved contract change); the reviewer's clean-checkout rule; lifecycle mapping from Orca task statuses (PENDING, READY, RUNNING, VALIDATING, REVIEW, COMPLETED, NEEDS_APPROVAL) |
| **Simulated** | the two repositories (throwaway, two cheap validation steps); Orca's Run, task ids and statuses (a recorded `task-list` response and a hand-written `orca-map.json`); the workers themselves (the script makes their commits); the review content |
| **Requires activation** | Orca's orchestration (Settings → Experimental); "Allow this host's orca CLI to control Orca" for the SSH host; the harness installed on tte-devbox-vlad; `tte-harness orca create` against a live Orca runtime; `tte-harness evidence pr` (calls `gh`); real worktrees under `/home/ubuntu/orca/workspaces/` |
| **Future** | creating the Users feature for real (a TTE ticket and `/req`); automatic delivery-report rendering from the run folder; contract-change gates raised by workers through `orca orchestration ask` handled by a dedicated harness command |

## Expected output of `simulate.sh` (trimmed)

```text
=== 3. Plan: validate the DAG, copy the pinned spec, write one brief per task
spec sha256:a5d51fc6f1f1bb8e895fe72380efd00f381ed40c5f7749d6e9bb7c69bb0e1941
wave 1: be-users-api, be-users-tests, fe-users-screen, fe-users-tests  (parallel)
wave 2: review-engine, review-frontend  (parallel)
wave 3: integration

=== 4. The Orca calls that would create the Run (printed, not executed)
orca orchestration run-create --objective 'Users management [users-management spec a5d51fc6f1f1]' --json --full
orca orchestration task-create --spec-file <run>/briefs/be-users-api.md --task-title 'be-users-api: GET /api/v1/users in tte-engine' --run '<orca-run-id>' --json --full
...
orca orchestration task-create --spec-file <run>/briefs/integration.md --task-title 'integration: ...' --deps '["<orca-id:review-engine>", "<orca-id:review-frontend>"]' --run '<orca-run-id>' --json --full
orca orchestration gate-create --question 'Open the pull requests for users-management ...' --options '["approve", "reject"]' --task '<orca-id:integration>' --json --full

=== 5. Status right after the Run is created: wave 1 ready, the rest waiting
READY           be-users-api                 backend-developer      tte-engine
...
PENDING         integration                  integration-engineer   tte-frontend

=== 6. be-users-tests: a QA worker oversteps (edits the contract) and leaves the tree dirty
head c57cbc94... dirty=True contract_changed=['openapi.json'] secrets=0
--- evidence check (must fail: dirty tree, contract changed, no review yet)
PASS   repo-validate          recorded
FAIL   clean-commit           the tree had uncommitted changes
PASS   spec-pinned            recorded
FAIL   no-contract-change     contract paths changed: openapi.json
PASS   no-secrets             recorded
FAIL   tests-cover-criteria   no review recorded (tte-harness evidence review)
FAIL   review-pass            no review recorded

=== 9. An independent reviewer records verdicts from clean checkouts
review pass on 4a968016... recorded for be-users-api
PASS   no-contract-change     recorded
PASS   security-reviewed      attested by the reviewer
PASS   review-pass            recorded
--- a reviewer cannot record a verdict from a modified checkout
tte-harness: .../repos/tte-engine has uncommitted changes. A reviewer reads and never edits; ...

=== 11. Status later: engine side reviewed, frontend in review, one worker owes evidence
COMPLETED       be-users-api                 backend-developer      tte-engine
COMPLETED       be-users-tests               backend-qa             tte-engine
REVIEW          fe-users-screen              frontend-developer     tte-frontend
VALIDATING      fe-users-tests               frontend-qa            tte-frontend
COMPLETED       review-engine                code-reviewer          tte-engine
RUNNING         review-frontend              code-reviewer          tte-frontend
NEEDS_APPROVAL  integration                  integration-engineer   tte-frontend

=== 12. The integration task's gates: PR and CI not recorded, merge approval is a person's
FAIL   pr-created             no pull request recorded (tte-harness evidence pr)
FAIL   ci-green               no pull request recorded
HUMAN  human-merge-approval   a person resolves the Orca decision gate; never an agent

=== Simulation passed: nothing outside <tmp> was touched
```
