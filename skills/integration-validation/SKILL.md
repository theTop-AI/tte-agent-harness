---
name: integration-validation
description: >-
  Use when independently developed and reviewed branches must be integrated per repository and
  checked together: merge task branches, resolve conflicts without changing behaviour, verify
  cross-repository contract compatibility, record validation, pull requests and CI, never merge.
metadata:
  category: delivery
  version: "1.0.0"
---

# Integration validation

Bring the reviewed work of each repository together, prove the repositories still agree on the
contract, and hand pull requests with green CI to a person. You integrate; you do not redesign.

## When to use

- An integration task brief, after the review tasks of the repositories it covers completed.
- Release validation across repositories (see the harness `release-validation` workflow).
- Not to fix review findings: those go back to the implementer through the coordinator.

## Inputs

- The task brief, the pinned spec and API contract, and the run folder's evidence for every task
  being integrated (`evidence/<task>/validation.json`, `review.json`).
- The reviewed commits: only commits with a passing review count.
- Each repository's PR conventions (tte-workflows: branch with the TTE key, Conventional title,
  `Docs-Updated:` and `Refs:` footers; `/make-pr` drives a delivery run's PR when one exists).

## Procedure

1. Confirm every task you integrate shows PASS for its development gates and `review-pass` in
   `tte-harness evidence check`. Stop at the first that does not.
2. Per repository, start the integration branch from the base branch and merge the reviewed
   commits of that repository's tasks (implementation and tests). Resolve conflicts by keeping
   both sides' intended behaviour; a conflict that needs a choice goes to the coordinator.
3. Contract compatibility across repositories:
   - the backend's committed contract (tte-engine `openapi.json`) contains the approved endpoints
     exactly as `api-contract.md` specifies;
   - the frontend reads the same shapes: its mocks and fixtures match the contract, and its
     pinned copy (tte-frontend `packages/api-engine/contract/`, a vendored engine document moved
     only by bumping `VERSION`, see its README and ADR-0001) is either unchanged or carries the
     approved change;
   - any mismatch is a finding. Never edit either side's contract to make them agree.
4. Validate each integration branch from its worktree:
   `tte-harness evidence run --run-dir <run> --task <your-task-id>`. Evidence is per task and
   per repository: if your brief covers a second repository, ask the coordinator for a task per
   repository rather than recording one repository's result over another's.
5. Push the integration branch and open the pull request in the repository's format. If the task
   carries an `approval:` gate, Orca holds it until a person allows this step.
6. `tte-harness evidence pr --run-dir <run> --task <your-task-id> --pr <url>`; re-record after CI
   finishes. `ci-green` needs every check on the head commit to pass.
7. Report the merge order. A backend contract change merges and releases first; the frontend's
   pin can move only to a released (or explicitly pinned) engine document, so a frontend PR that
   depends on it either runs on the mock until then or waits.

## Outputs

- One integration branch and pull request per repository, with validation and PR evidence.
- A report: PR links, CI state on each head, contract compatibility result, merge order,
  unresolved findings.

## Validation

- `tte-harness evidence check` passes for your task's development and delivery gates.
- The PR head is the validated commit (`pr-created` fails otherwise: validate again).
- No contract path changed except by the approved change.

## Escalate when

- A conflict needs a behavioural decision, or the repositories disagree about the contract.
- CI fails on something the integrated tasks did not touch (report it with the run link).
- Anything would require merging, force-pushing, or pushing to a protected branch.
