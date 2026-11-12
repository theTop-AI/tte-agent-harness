# Feature development

Spec first, then parallel work per repository, then integration, independent review and a
person's merge. Use it for any feature that changes behaviour in one or more product
repositories; [workflow.yaml](workflow.yaml) is the machine-checked version of this page.

## Stages

| # | Stage | Role | Runs where | Waits for | Gates |
|---|---|---|---|---|---|
| 1 | requirements | solution-architect | a session in the feature's spec repository | — | — |
| 2 | architecture (+ API contract, test plan) | solution-architect | same session | 1 | — |
| 3 | decomposition (`plan.yaml`) | solution-architect | same session | 2 | — |
| 4 | spec-approval | **person**, via the coordinator | Orca decision gate or review of the spec PR | 3 | — |
| 5 | backend, backend-tests | backend-developer, backend-qa | Orca workers, one worktree each | 4 | development + `review-pass` |
| 5 | frontend, frontend-tests | frontend-developer, frontend-qa | Orca workers, one worktree each | 4 | development + `review-pass` |
| 6 | review (per repository) | code-reviewer | Orca worker, clean worktree of the branch | 5 | `scope-matches-task`, `security-reviewed`, `tests-cover-criteria` |
| 7 | integration | integration-engineer | Orca worker per repository | 6 | `pr-created`, `ci-green` |
| 8 | delivery | coordinator, then **person** | coordinator session | 7 | `acceptance-verified`, `risks-documented`, `human-merge-approval` |

Development gates: `repo-validate`, `clean-commit`, `spec-pinned`, `no-contract-change`,
`no-secrets` ([config/quality-gates.yaml](../../config/quality-gates.yaml)). The four stage-5
tasks start together: QA writes tests against the approved contract while the developers build,
which is why the contract is approved before anything else.

## Step by step

1. **Spec (stages 1–3).** Start a Claude Code or Codex session as the `solution-architect` and give
   it the request. It writes `spec/requirements.md`, `spec/architecture.md`,
   `spec/api-contract.md`, `spec/test-plan.md` and `plan.yaml` in the feature folder, from
   [templates/](../../templates/). Check the plan: `tte-harness plan <feature>/plan.yaml --check`.
2. **Approval (stage 4).** A person reads the spec and the plan. On approval:
   `tte-harness spec lock <feature>/spec --approved-by "<name>"`. Commit the lock with the spec.
   From here the spec is frozen; a change is a new version and a new approval.
3. **Run (stage 4 → 5).** In Orca, start the `coordinator` (a session with Orca's
   `orchestration` skill loaded) and point it at the feature folder. It runs
   `tte-harness plan <feature>/plan.yaml` (run folder, pinned spec copy, one brief per task) and
   `tte-harness orca create --run-dir <run>` (the Orca Run and one Task per plan task).
4. **Workers (stage 5).** The coordinator starts a worker for every ready task with
   `orca orchestration worker-start --task <id> --worktree new-top-level --repo <repo> --agent
   claude|codex` and ends its turn. Each worker gets its brief, works in its own worktree, and
   proves completion with `tte-harness evidence run` and `evidence check`.
5. **Evidence before dependents.** On each `worker_done` the coordinator runs
   `tte-harness evidence check --run-dir <run> --task <id>`. Any FAIL row sends the worker back.
6. **Review (stage 6).** A different worker, as `code-reviewer`, reviews each repository's
   branches from a clean worktree and records the verdict with `tte-harness evidence review`.
7. **Integration (stage 7).** The `integration-engineer` merges the reviewed branches per
   repository, validates frontend and backend together, opens the pull requests and records them
   with `tte-harness evidence pr`.
8. **Delivery (stage 8).** The coordinator writes the delivery report from
   [templates/delivery-report.md](../../templates/delivery-report.md); `tte-harness status
   --run-dir <run>` gives every task's lifecycle state. A person merges, in the order given.

## Where Orca does what

Orca owns the Run, the Tasks and their dependencies, the worker sessions and worktrees, the mail
between coordinator and workers, and the decision gates. The harness owns the spec lock, the
briefs, the evidence and the mapping of Orca statuses onto the lifecycle. No harness code starts,
stops or watches a worker.

## Human only

- Approving the spec (stage 4) and every later change to it.
- Resolving decision gates, including opening pull requests where the plan gates it.
- Merging. No agent merges; the harness permission rules deny `gh pr merge`.
- Deploys, `terraform apply`, releases and tags.
