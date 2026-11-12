---
name: frontend-testing
description: >-
  Use when frontend behaviour needs tests or a test-first suite: component, integration and E2E
  scenarios from acceptance criteria, covering positive, negative, boundary, permission and
  accessibility cases, with reproducible failure reports (tte-frontend: Vitest, Testing Library,
  msw, Playwright).
metadata:
  category: quality
  version: "1.0.0"
---

# Frontend testing

Prove each acceptance criterion from the user's side, at the cheapest level that can observe it,
and report every failure so someone else can reproduce it in one command.

## When to use

- A frontend QA task brief: write the tests for a feature, before or beside the implementation.
- A regression or accessibility issue needs a failing test before the fix.
- Not for backend contract tests (`backend-testing`).

## Inputs

- The task brief with the pinned acceptance criteria, API contract and `test-plan.md` rows.
- The repository's test setup, read before writing a test. tte-frontend: `apps/web/vitest.config.ts`
  (unit tests do not load the Start plugin), `apps/web/playwright.config.ts` (e2e against a
  production build), `apps/web/e2e/mock-engine.ts` (the engine stand-in), existing specs in
  `apps/web/e2e/`.

## Procedure

1. Map each AC to a level: component (Vitest + Testing Library) for rendering and states,
   integration with mocked HTTP (msw) for data flows, E2E (Playwright, mock engine) for journeys
   across routes. Prefer the lowest level that observes the behaviour.
2. For each AC write the cases in [the scenario matrix](references/scenario-matrix.md):
   positive, negative, boundary, permission, isolation, accessibility, regression.
3. Test first: when the implementation does not exist yet, write the tests against the
   contract and the mock, run them, and confirm they fail for the right reason (missing route or
   element), not for a setup error. Commit them so the developer's branch can pick them up.
4. Query by role and accessible name, not by class or test id, unless the repository's tests
   already settle on another convention.
5. Data comes from fixtures derived from the contract (mock engine handlers, msw handlers), never
   from a live service.
6. No sleeps: wait for a visible state. No test depends on another's order.
7. Run the repository's test commands; for a failure, write a report in the format below.
8. Commit, then `tte-harness evidence run` and `tte-harness evidence check`.

Failure report (one per failure): test id and file, the command that reproduces it, expected vs
actual, the first failing assertion, a screenshot or trace path for E2E, and whether it fails on
the base branch too.

## Outputs

- Test files on the task branch, each test titled with the AC id it proves (`AC-2: ...`).
- A coverage note: AC id to test name, and any AC no test can observe (with the manual check).
- Failure reports for every red test that is not expected to be red.

## Validation

- Every AC the task carries has at least one test; every negative and permission case in the
  test plan is present.
- Tests pass against the finished implementation, and test-first tests failed before it existed.
- The repository's validation sequence passes, including e2e when its paths changed.

## Escalate when

- An AC cannot be observed at any level (say so and propose the manual check).
- The mock engine or fixtures cannot represent the contract without changing shared test code
  other features depend on.
- A test is flaky locally: report it with the evidence; do not retry until green.
