# <Feature title> — test plan

Feature id: `<feature-id>` · Requirements: `requirements.md` · Contract: `api-contract.md`

## Strategy

Which levels carry which risk: unit, component, API/integration, contract, end-to-end. Use the
repositories' existing frameworks only (name them, with the file that shows each).

## Scenarios

One row per scenario; every acceptance criterion appears at least once.

| ID | AC | Level | Repository | Kind | Scenario | Expected |
|---|---|---|---|---|---|---|
| T-1 | AC-1 | API | backend | positive | | |
| T-2 | AC-1 | API | backend | negative | | |
| T-3 | AC-1 | API | backend | boundary | | |

Kinds: positive, negative, boundary, authorization, isolation, accessibility, regression.

## Test data

Fixtures, seeded tenants and users, and how they are created and cleaned up.

## Environments

Where each level runs (local, CI, mock engine, dev) and what it needs.

## Test-first order

Which tests QA writes before the implementation exists, and how they are kept failing for the
right reason until it does.

## Exit criteria

All scenarios pass in CI on the pull request head; no skipped test without a ticket.
