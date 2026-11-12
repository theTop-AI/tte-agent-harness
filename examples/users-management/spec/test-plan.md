# Users management — test plan

Feature id: `users-management` · Requirements: `requirements.md` · Contract: `api-contract.md`

## Strategy

| Level | Repository | Framework (as the repository uses it) | Carries |
|---|---|---|---|
| Unit | tte-engine | pytest (`make test`) | query building, cursor encode/decode, filters |
| API / integration | tte-engine | pytest with the test database (`make test-up`, `CONTEXTBANK_REQUIRE_DB_TESTS=1`) | the contract, authorization, tenant isolation |
| Contract | tte-engine | `scripts/export_openapi.py --check` | `openapi.json` matches the routers |
| Component | tte-frontend | Vitest + Testing Library (`pnpm turbo run test`) | filter bar, table states |
| End to end | tte-frontend | Playwright against `@tte/mock-engine` (`pnpm turbo run test:e2e`) | the screen against the pinned contract |

## Backend scenarios

| ID | AC | Level | Kind | Scenario | Expected |
|---|---|---|---|---|---|
| B-1 | AC-1 | API | positive | admin lists an org with 3 members | 200, 3 rows, every field per contract |
| B-2 | AC-2 | API | positive | `q=ada` | only Ada; case-insensitive |
| B-3 | AC-3 | API | positive | `role=viewer` | only viewers |
| B-4 | AC-4 | API | boundary | 120 members, `limit=50`, follow `next_cursor` | 50+50+20, no duplicates, last `next_cursor` null |
| B-5 | AC-4 | API | boundary | `limit=0`, `limit=201` | 400 `bad_param`, `param: limit` |
| B-6 | AC-4 | API | negative | a cursor from `/identity/principals` | 400 `bad_param`, `param: cursor` |
| B-7 | AC-5 | API | authorization | a non-admin credential | 403 `forbidden` |
| B-8 | AC-5 | API | isolation | org B's member id never appears for org A, under every filter | absent |
| B-9 | NFR-2 | API | negative | response schema | no credential or content field |
| B-10 | AC-6 | API | positive | `q` matching nobody | 200, `rows: []`, `total: 0` |

## Frontend scenarios

| ID | AC | Level | Kind | Scenario | Expected |
|---|---|---|---|---|---|
| F-1 | AC-1 | e2e | positive | open Users as admin | rows with name, email, role, status, last sign-in |
| F-2 | AC-2 | component | positive | type "ada" | list narrows; query in URL |
| F-3 | AC-3 | e2e | positive | role filter = viewer | only viewers; reload keeps the filter |
| F-4 | AC-4 | e2e | boundary | 120 fixture members | "Load more" twice, then gone |
| F-5 | AC-6 | component | negative | no match | empty state with "Clear search" |
| F-6 | AC-6 | e2e | negative | mock engine answers 503 | error state with retry |
| F-7 | AC-7 | component | positive | `freshness.state = stale` | stale notice |
| F-8 | NFR-3 | e2e | accessibility | keyboard only | search, filter, table and Load more reachable; axe finds no violations |

## Test data

Engine: three seeded orgs (A with 3 members, B with 1, C with 120) created per test through the
repository's existing fixtures. Frontend: a `users` fixture in `@tte/mock-engine` generated from the
pinned contract, plus a 120-member scenario tenant.

## Environments

Engine tests run locally and in CI with the test database. Frontend component tests run in Vitest;
e2e runs Playwright against the mock engine on port 4310, as the suite already does.

## Test-first order

QA tasks start in wave 1 beside the implementation: backend QA writes B-1…B-10 against the contract
and keeps them failing on "404 route not found" until the route exists; frontend QA writes F-1…F-8
against the mock engine fixture and keeps them failing on the missing route `/users`. A test that
fails for any other reason is a defect in the test.

## Exit criteria

All scenarios pass in CI on the pull request head of each repository; no skipped test without a
ticket.
