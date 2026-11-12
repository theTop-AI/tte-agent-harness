---
name: task-decomposition
description: >-
  Use when an approved architecture must become an executable task graph: plan.yaml with one
  task per role and repository, explicit dependencies, parallel waves, test-first QA tasks,
  review tasks and quality gates, validated with `tte-harness plan --check`.
metadata:
  category: planning
  version: "1.0.0"
---

# Task decomposition

Split a feature into tasks that independent workers can finish in separate worktrees without
talking to each other, and make every real dependency explicit so nothing pretends to be
parallel that is not.

## When to use

- `requirements.md`, `architecture.md` and `api-contract.md` exist and are ready for approval.
- A plan must change because a task turned out to be two, or a dependency was missed.
- Not for one-file changes a single session finishes alone.

## Inputs

- The spec folder: requirements, architecture (its Delivery shape section), API contract,
  test plan.
- `templates/plan.yaml` in the harness checkout: the schema, with every key explained.
- The repository registry (`tte-harness repos`): which roles may work in which repository.
- The quality gates in `config/quality-gates.yaml` of the harness checkout.

## Procedure

1. One task = one role in one repository with one deliverable. A task that spans two
   repositories is two tasks with a dependency.
2. Start from the contract: once it is approved and locked, backend, frontend and both QA tasks
   depend only on it, not on each other, so they form the first wave.
3. Add QA tasks that write tests first, beside the implementation, against the contract and the
   acceptance criteria; they do not depend on the implementation task.
4. Add one `code-reviewer` task per repository that depends on that repository's implementation
   and test tasks; point each reviewed task's `review_by` at it.
5. Add the integration task after the reviews. Put an `approval:` question on any task whose
   start needs a person (opening pull requests, a risky migration).
6. For each task fill every required key: `id`, `title`, `role`, `repo`, `depends_on`,
   `inputs` (spec files, narrowed with `file.md#heading-anchor`), `outputs`, `gates`,
   `done_when`, `status: PENDING`, `blockers: []`. Rules: [plan rules](references/plan-rules.md).
7. Give implementation tasks the development gates plus `review-pass`; give a task that
   implements the approved contract change `contract_change: approved`, and nobody else.
8. Run `tte-harness plan <feature>/plan.yaml --check` and fix every error. Then read the waves
   that `tte-harness plan` prints and check each one is truly independent.

## Outputs

- `<feature>/plan.yaml` that passes `tte-harness plan --check`.
- A short note of the waves and the critical path, for the person approving the plan.

## Validation

- Every acceptance criterion is in the `done_when` or `inputs` of at least one task.
- No cycle; no task depends on a task only for convenience.
- Every implementation task has a review task, and every review task depends on what it reviews.
- Every `inputs` entry resolves to a file and heading in the spec folder.

## Escalate when

- A dependency cannot be removed and serialises most of the work: say so; do not hide it.
- A role needed for a task is not allowed in that repository (`roles` in the registry).
- The architecture leaves a decision open that two tasks would each make differently.
