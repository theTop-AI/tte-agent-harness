# Code review

A second, independent read of a change that already exists: a pull request someone opened, or a
branch an agent produced outside a feature run. The reviewer never edits; fixes go back to the
developer role, and a person decides on the merge. [workflow.yaml](workflow.yaml) is the checked
version of this page.

## Stages

| # | Stage | Role | Waits for | Gates |
|---|---|---|---|---|
| 1 | review | code-reviewer | — | `scope-matches-task`, `security-reviewed`, `tests-cover-criteria` |
| 2 | fix-backend / fix-frontend (optional) | backend-developer / frontend-developer | 1 | `repo-validate`, `clean-commit`, `no-contract-change`, `no-secrets`, `review-pass` |
| 3 | re-review | code-reviewer | 2 | as stage 1 |
| 4 | report | coordinator, then **person** | 3 | `risks-documented`, `human-merge-approval` |

When the first review passes with no findings worth fixing, the plan drops stages 2 and 3.

## Step by step

1. **Spec.** For a review the "spec" is the review request: the pull request or branch, what it
   claims to do, the ticket, and what deserves particular attention. Put it in `spec/` (a short
   `requirements.md` is enough), lock it with `tte-harness spec lock`, and write `plan.yaml`.
2. **Review.** The coordinator starts a `code-reviewer` worker in a fresh worktree of the branch
   (`worker-start --worktree new-top-level --repo <repo> --base-branch <branch>`). The reviewer
   reads the diff, the ticket and the code around it, writes findings by severity with file and
   line, and records the verdict from that clean worktree:
   `tte-harness evidence review --run-dir <run> --task review-<repo> --verdict pass|fail
   --critical <n> --findings findings.md --attest scope-matches-task,security-reviewed,tests-cover-criteria`.
3. **Fix loop.** For a fail, a developer worker of the repository's role fixes the findings on the
   same branch, then validates with `tte-harness evidence run`. Disagreeing with a finding is
   allowed: the developer says why in its report and the coordinator brings it to a person.
4. **Re-review.** A reviewer session that did not write the fixes reviews the new head. A verdict
   counts only for the commit it read.
5. **Report.** The coordinator summarises the verdict, the resolved and open findings, and the
   evidence, from [templates/delivery-report.md](../../templates/delivery-report.md).

## Where Orca does what

Orca gives each reviewer and developer its own worktree and session, carries the findings between
them as mail, and keeps the Run. The harness records the verdicts and checks them against the
validated commit.

## Human only

Deciding to merge, overriding a finding, and approving anything outward-facing.
