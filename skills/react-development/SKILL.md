---
name: react-development
description: >-
  Use when implementing or changing React UI in a frontend repository: screens, routes,
  components, data fetching and state against an approved API contract, following the
  repository's own architecture, design rules and tests (tte-frontend: TanStack Start, Tailwind
  v4, shadcn/ui).
metadata:
  category: development
  version: "1.0.0"
---

# React development

Build the screen the spec describes, in the shape the repository already uses, reading data
only through the contract the feature pinned.

## When to use

- A frontend task brief asks for a new screen, route, component or a change to one.
- A frontend test or review finding needs a code fix.
- Not for writing the test suite itself (`frontend-testing`), nor for changing the API contract.

## Inputs

- The task brief: pinned spec digest, quoted requirements, API contract, acceptance criteria.
- The repository's rules, read before any edit. tte-frontend: `AGENTS.md`,
  `docs/CONVENTIONS.md`, `docs/architecture/apps-web.md` (layers, feature anatomy, import
  rules), `apps/web/DESIGN.md` (visual rules), `apps/web/PRODUCT.md` (product rules).
- The repository's API client layer (tte-frontend: `packages/api-engine`, generated from the
  pinned `openapi.json`; never call the engine around it).

## Procedure

1. Find the closest existing screen or component and follow its structure: route file, feature
   folder, data hooks, loading and error states. Name it in your report.
2. Data: read through the repository's client and query layer (tte-frontend: TanStack Query via
   `packages/api-engine`). Types come from the generated contract, never hand-written copies.
3. If the contract the feature approved is not in the generated client yet (the engine has not
   released it), build against the mock the repository provides for that purpose (tte-frontend:
   `apps/web/e2e/mock-engine.ts`) and say so; do not edit generated files by hand.
4. States: every data view has loading, empty, error and permission-denied states as the
   requirements specify. Follow the repository's product rules for numbers and labels
   (tte-frontend: every number carries its freshness from `meta.freshness`; labels describe
   consequences, not mechanisms).
5. UI: use the repository's component library and tokens (tte-frontend: shadcn/ui in
   `packages/ui`, Tailwind v4 tokens from `packages/tokens`); no one-off colours or spacing.
6. Accessibility: semantic elements, labels on every control, keyboard path, focus after
   navigation, contrast from the tokens.
7. Write or update the component and route tests the brief asks for; the QA task covers the
   wider suite.
8. Commit, then `tte-harness evidence run` and `tte-harness evidence check` from the worktree root.

## Outputs

- Commits on the task branch: route, components, hooks, tests, and the docs the repository's
  AGENTS.md requires for the kind of change (tte-frontend: its documentation table).
- Evidence recorded in the run folder; a `worker_done` report naming any mock still in use.

## Validation

- The repository's whole validation sequence passes (`.claude/project.json`: lint, format,
  typecheck, unit tests, build, and e2e when its paths changed).
- No change under the repository's `contract_paths` unless the task carries the approved change.
- Every acceptance criterion the task carries is visible in the running screen or a test.

## Escalate when

- The contract lacks a field the screen needs, or returns data the product rules forbid showing.
- The design rules do not cover the case (a new pattern, a new token).
- The change would touch another feature's files or the shared client layer beyond the task.
