---
name: backend-testing
description: >-
  Use when backend behaviour needs API, integration or contract tests, or a test-first suite:
  request/response contract checks, authorization and tenant isolation, validation, pagination,
  filtering and error handling, with coverage gaps and failures reported reproducibly
  (tte-engine: pytest).
metadata:
  category: quality
  version: "1.0.0"
---

# Backend testing

Prove that the server honours the pinned contract for every caller, and especially for the ones
who must be refused. A missing negative test is a finding, not a style note.

## When to use

- A backend QA task brief: write the API and integration tests for a feature, before or beside
  the implementation.
- A review found a gap in authorization, isolation or error handling that needs a test.
- Not for UI tests (`frontend-testing`).

## Inputs

- The task brief with the pinned API contract, acceptance criteria and `test-plan.md` rows.
- The repository's test setup, read before writing a test. tte-engine: `pyproject.toml`
  (`[tool.pytest.ini_options]`), `tests/` and its fixtures, `make test-up` / `make test` for the
  test database; existing contract tests such as `tests/test_api_contract.py`.

## Procedure

1. List every endpoint in the contract and, for each, the cases in
   [the API test matrix](references/api-test-matrix.md). That list is your coverage map.
2. Build data through the repository's fixtures: at least two tenants, a user with the
   permission and one without, and enough rows to cross a page boundary.
3. Assert the whole contract shape on success: status, every field and its type, nullability,
   and that no field outside the contract is present (a leak is a failure).
4. Test first: when the endpoint does not exist yet, write the tests against the contract, run
   them, and confirm they fail because the route is missing, not because of a fixture error.
5. Authorization and isolation: every endpoint gets an unauthenticated call, a caller without
   the permission, and a caller from another tenant asking for an id that exists elsewhere.
6. Lists: first page, last page, empty, maximum page size, page size over the maximum, every
   filter and sort key, and an unknown filter or sort key.
7. Run the repository's test commands. For each failure write a report: test id, command that
   reproduces it, request sent, expected vs actual response, and whether it fails on the base
   branch.
8. Commit, then `tte-harness evidence run` and `tte-harness evidence check`.

## Outputs

- Test files on the task branch, each test named with the AC or contract endpoint it proves.
- A coverage note: endpoint x case table, with every gap named and the reason.
- Failure reports for unexpected failures.

## Validation

- Every endpoint has positive, validation, permission, cross-tenant and (for lists) pagination
  tests.
- Tests pass against the finished implementation; test-first tests failed before it existed.
- The repository's whole validation sequence passes (tte-engine runs the tests with a database).

## Escalate when

- The contract and the requirements disagree about a case; do not pick one.
- A case cannot be tested without a fixture or service the repository does not have.
- The implementation passes a test the contract says should fail (report it as a defect).
