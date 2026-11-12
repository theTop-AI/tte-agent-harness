---
name: tte-code-review
description: >-
  Use when a change must be reviewed independently before integration: read the diff against
  the base, the task brief and the pinned spec yourself, ignore the implementer's summary, rate
  findings critical/major/minor/nit with file:line evidence, and record the verdict with
  `tte-harness evidence review`.
metadata:
  category: quality
  version: "1.0.0"
---

# Code review (harness)

Named `tte-code-review` because Claude Code bundles its own `/code-review`; this one reviews a
harness task against its brief and pinned spec and records a verdict the gates can read.

The implementer's account of what they did is a claim to check, not evidence. Read the code.

## When to use

- A `code-reviewer` task brief: review another task's branch in the same repository.
- A person asks for an independent review of a task branch before it is integrated.
- Not to fix the code: findings go back to the implementer through the coordinator.

## Inputs

- The brief of the task under review and its pinned spec (the run folder's `spec/` copy).
- The validated commit: `head` in `<run-dir>/evidence/<task>/validation.json`.
- The repository's rules: `AGENTS.md`, `CONTRIBUTING.md`, the docs its AGENTS.md lists.

## Procedure

1. Check out exactly the validated commit in a clean worktree. Never review a moving branch.
2. Read the brief's scope and `done_when`, then the whole diff against the merge-base with the
   base branch (`git diff <merge-base>..<head>`). Note files that the task should not touch.
3. Check correctness against the spec, not against the description: every AC the task carries,
   every contract field, every error case.
4. Architecture: the change follows the repository's existing patterns and the approved
   architecture decisions; no new pattern without a reason.
5. Security: run the `tte-security-review` procedure over the diff.
6. Tests: every AC and every negative case of the test plan has a test that would fail without
   the change. Run the repository's tests yourself if the evidence looks thin.
7. Complexity: dead code, duplication, abstractions with one caller, unrelated refactors.
8. Write findings in [the review report format](references/review-report.md), each with severity
   and file:line evidence. Critical: wrong behaviour, security or isolation defect, contract
   change, data loss. Major: missing test for an AC, scope creep, broken convention. Minor and
   nit: everything else.
9. Record the verdict from the clean checkout:
   `tte-harness evidence review --run-dir <run> --task <reviewed-task> --verdict pass|fail
   --critical <n> --findings <report.md> --attest scope-matches-task,security-reviewed,tests-cover-criteria`
   (attest only the gates you actually checked). `pass` needs zero unresolved critical findings.

## Outputs

- The review report file and the recorded verdict in `<run-dir>/evidence/<task>/review.json`.
- A `worker_done` report: verdict, counts per severity, the critical findings in full.

## Validation

- Every finding has a severity, a file:line and a concrete reason; no "consider improving".
- The verdict was recorded for the same commit the evidence validated.
- Your worktree has no changes: `evidence review` refuses a dirty tree, because reviewers read.

## Escalate when

- The diff changes a contract path without `contract_change: approved` on the task.
- The change is correct but the spec is wrong: raise it to the coordinator; do not pass or fail
  the code for the spec's fault.
- You cannot run or read something needed to judge (missing access, secrets): say what is missing.
