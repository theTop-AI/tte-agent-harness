# Bug fixing

A defect is fixed when a test that failed for the reported reason now passes, a different session
reviewed the fix, and a person merged it. Use this for a reported defect in one or more product
repositories; [workflow.yaml](workflow.yaml) is the checked version of this page.

## Stages

| # | Stage | Role | Waits for | Gates |
|---|---|---|---|---|
| 1 | triage | solution-architect | — | — |
| 2 | scope-approval | **person**, via the coordinator | 1 | — |
| 3 | reproduce-backend / reproduce-frontend | backend-qa / frontend-qa | 2 | `clean-commit`, `spec-pinned`, `no-contract-change`, `no-secrets` |
| 4 | fix-backend / fix-frontend | backend-developer / frontend-developer | its reproduce stage | development gates + `review-pass` |
| 5 | review | code-reviewer | 4 | `scope-matches-task`, `security-reviewed`, `tests-cover-criteria` |
| 6 | integration | integration-engineer, after a decision gate | 5 | `pr-created`, `ci-green` |
| 7 | report | coordinator, then **person** | 6 | `acceptance-verified`, `risks-documented`, `human-merge-approval` |

Keep the stages of the side that is broken. A frontend-only defect drops the backend stages; a
contract defect usually needs both, and then the contract change goes through approval first
(the architect revises `api-contract.md`, a person approves, `tte-harness spec lock` pins it).

## Step by step

1. **Triage.** The `solution-architect` writes `spec/requirements.md` as a bug analysis: steps to
   reproduce, actual versus expected behaviour, affected repository and the acceptance criterion
   the fix must meet. It writes `plan.yaml` with only the stages that apply.
2. **Scope approval.** A person approves; `tte-harness spec lock <bug>/spec --approved-by "<name>"`.
3. **Reproduce.** The QA worker writes a test that fails on the base branch *for the reported
   reason* and commits it. Its evidence deliberately skips `repo-validate`, because the suite is
   red on purpose; the report quotes the failing assertion.
4. **Fix.** The developer works on top of the reproducing branch. `tte-harness evidence run` must
   now pass the whole validation sequence, including the new test.
5. **Review.** A `code-reviewer` worker checks the fix addresses the root cause, not the symptom,
   and that the test would fail without it; it records the verdict with
   `tte-harness evidence review`.
6. **Integration.** After the decision gate, the `integration-engineer` opens the pull request
   and records it with `tte-harness evidence pr`.
7. **Report.** The coordinator's delivery report names the root cause, the fix, the test that
   proves it and any related places with the same defect.

## Where Orca does what

Orca runs each stage's worker in its own worktree, carries questions and `worker_done` reports,
and holds the decision gates. `tte-harness plan`, `orca create`, `evidence` and `status` are the
same commands as in [feature development](../feature-development/README.md).

## Human only

Approving the fix scope, resolving the pull-request gate, merging, and anything released or
deployed afterwards.
