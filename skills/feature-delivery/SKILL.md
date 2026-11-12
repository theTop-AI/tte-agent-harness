---
name: feature-delivery
description: >-
  Use when coordinating a multi-task or multi-repository feature through Orca: lock the approved
  spec, prepare the run with `tte-harness plan`, create the Orca task DAG, start workers on ready
  tasks, gate dependents on recorded evidence, escalate contract changes, report, never merge.
metadata:
  category: delivery
  version: "1.0.0"
---

# Feature delivery (coordinator)

You run the delivery; Orca runs the workers. Orca keeps the Run, Tasks, workers and mail. The
harness pins the spec, writes the briefs and decides from recorded evidence whether a task is
really done. You decide nothing that belongs to a person.

## When to use

- A feature folder has `spec/` and `plan.yaml` from the architect, and the work spans several
  tasks or repositories.
- You were started as the coordinator of an existing run (resume from `tte-harness status`).
- Not for a change one session can finish alone: do that directly.

## Inputs

- `<feature>/spec/` (requirements, architecture, API contract, test plan) and `<feature>/plan.yaml`.
- Orca's version-matched orchestration guide: run `orca skills get orchestration` once and follow
  it (and its references when it names a gate) for every Orca command beyond those below.
- The harness CLI on this host: `tte-harness` (`tte-harness doctor` says whether Orca's runtime
  and orchestration answer).

## Procedure

1. **Approval.** Show the person the spec and the plan's waves (`tte-harness plan <plan> --check`
   lists errors; fix them with the architect first). Only on their explicit approval run
   `tte-harness spec lock <feature>/spec --approved-by "<their name>"` and commit the lock with
   the spec. No approval, no lock, no workers.
2. **Prepare.** `tte-harness plan <feature>/plan.yaml --run-dir <run>`: it refuses a spec that
   changed since the lock, copies the pinned spec read-only into the run, writes one brief per
   task and prints the parallel waves.
3. **Create the DAG.** `tte-harness orca commands --run-dir <run>` shows the calls;
   `tte-harness orca create --run-dir <run>` makes the Run, one Task per plan task with its
   dependencies, and a decision gate for each `approval:`. Ids land in `<run>/orca-map.json`;
   pass `--run <run_id>` on later Orca commands.
4. **Start ready work.** `orca orchestration task-list --ready --run <run_id>`. For each ready
   task start a worker in a fresh worktree of the task's repository:
   `orca orchestration worker-start --task <orca-task-id> --run <run_id> --worktree new-top-level
   --repo id:<repoId> --name <task-id> --agent claude` (or `--agent codex`; `orca repo list --json`
   gives `repoId`). Workers on a paired server take `--on <server>` and that server's exact repo
   selector: load the guide's placement reference first. Then end your turn: Orca wakes you.
5. **On every wake** follow [the coordinator loop](references/coordinator-loop.md): answer
   questions from the spec or ask the person; for each `worker_done`, run
   `tte-harness evidence check --run-dir <run> --task <task-id>` before starting anything that
   depends on it. A FAIL row means the task is not done, whatever the worker said.
6. **Contract changes.** A worker that needs the contract changed stops and asks. Open a
   decision gate on the affected task (`orca orchestration gate-create --task <id> --question ...
   --options '["approve","reject"]'`), tell the person, and wait. On approval the architect
   revises `api-contract.md`, the person approves again, you re-lock, re-plan and restart the
   affected tasks with the new briefs. Never edit the contract or the spec yourself.
7. **State.** `tte-harness status --run-dir <run>` maps Orca's task statuses and the evidence
   onto the harness lifecycle (PENDING, READY, RUNNING, VALIDATING, REVIEW, COMPLETED, BLOCKED,
   NEEDS_APPROVAL, FAILED, CANCELLED). Report states from it, never from a worker's message.
8. **Deliver.** When every task is COMPLETED or explicitly given up, write the report from
   `templates/delivery-report.md`: task states, evidence results, pull requests with CI on their
   head commits, AC verification, open findings and risks, and the merge order. Hand it to the
   person. A person merges; you never do.

## Outputs

- The spec lock (committed), the run folder, the Orca Run with its Tasks and gates.
- A delivery report with PR links and the decisions the person must take.

## Validation

- Every task reported COMPLETED passes `tte-harness evidence check` with no FAIL row.
- No dependent task started before its dependencies passed their development gates.
- Every human gate was resolved by a person, recorded in Orca, never by you.

## Escalate when

- Any question the spec does not answer, any contract change, any scope change.
- A task fails three starts (Orca's breaker) or its evidence keeps failing for reasons outside it.
- A worker's report and the evidence disagree, or a worker touched another task's repository.
