# Coordinator loop

What to do each time Orca wakes the coordinator. Orca commands are from the version-matched
guide (`orca skills get orchestration`); if a flag below is refused, that guide wins.

## On each message

| Message | Do |
|---|---|
| `question` from a worker | If the answer follows from the pinned spec or the brief, reply: `orca orchestration reply --id <message_id> --body "<answer, citing the spec section>"`. Otherwise ask the person, then reply with their words. |
| `worker_done`, outcome succeeded | `tte-harness evidence check --run-dir <run> --task <task-id>`. All development gates PASS: the task may unblock dependents. Any FAIL: do not start dependents; send the failing rows back (`orca orchestration send --to dispatch:<dispatch_id> --subject "evidence" --body "<rows>"`) or mark it failed (next row). |
| `worker_done`, outcome failed | Never mark it completed. Read the reason; fix the brief or the plan with the architect, or retry the same task per the guide's recovery reference (`worker-start --task <id> --retry-of <dispatch_id> ...`). |
| `escalation` with `stopReason` | The worker stopped without reporting: steer it with `send`, stop and retry it, or tell the person. Silence never proves it stopped. |
| a contract-change request | Decision gate on the task, tell the person, wait (see SKILL.md step 6). |

## After the messages

1. `orca orchestration task-list --ready --run <run_id>` and start a worker for each ready task
   whose dependencies passed `evidence check`.
2. If a completed task's evidence failed, set it back so dependents do not start:
   `orca orchestration task-update --id <orca-task-id> --status failed --result "evidence: <gate>: <reason>"`
   and retry it with `--retry-of`.
3. `tte-harness status --run-dir <run>`; end your turn. Never poll and never run a watch script:
   a consuming `check` in a script takes mail you would never see.

## Lifecycle, as `tte-harness status` derives it

| Harness state | Orca task status | Plus |
|---|---|---|
| PENDING | pending | dependencies not done |
| READY | ready | start a worker |
| RUNNING | dispatched | a worker holds it |
| VALIDATING | completed | development gates not passing yet |
| REVIEW | completed | development gates pass; its review task or review gates not done |
| COMPLETED | completed | review task completed and every non-human gate passes |
| BLOCKED | blocked | waiting on something outside the DAG |
| NEEDS_APPROVAL | blocked | the task has an open decision gate |
| FAILED | failed | worker failure or evidence failure |
| CANCELLED | failed | result starts with "cancelled" (stop the worker first, per the guide) |

## Never

- Merge, push to `main`, deploy, resolve a gate on a person's behalf, edit the spec or contract,
  or start a dependent of a task whose evidence fails.
- Run `orca orchestration reset` (it deletes coordination state; only a person decides that).
