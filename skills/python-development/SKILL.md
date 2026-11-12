---
name: python-development
description: >-
  Use when implementing or changing Python backend code: FastAPI routes, services, data access,
  migrations and their tests, with typed models, tenant-scoped queries and the repository's own
  lint and test tooling (tte-engine: uv, ruff, pytest, committed openapi.json).
metadata:
  category: development
  version: "1.0.0"
---

# Python development

Implement backend behaviour that matches the pinned contract exactly, keeps every tenant's data
apart, and passes the repository's own checks on the committed tree.

## When to use

- A backend task brief asks for an endpoint, a service change, a job or a migration.
- A backend test or review finding needs a code fix.
- Not for designing the API (`api-design`) or writing the wider test suite (`backend-testing`).

## Inputs

- The task brief: pinned spec digest, the quoted API contract, acceptance criteria, gates.
- The repository's rules, read before any edit. tte-engine: `AGENTS.md` (including its table of
  documents a change must update), `CONTRIBUTING.md`, `docs/system/ARCHITECTURE.md`.
- The existing router, schema, service and data-access code nearest to the change.

## Procedure

1. Find the closest existing endpoint and follow its layering: router, request and response
   models, service, data access, error mapping. Name it in your report.
2. Models: request and response schemas are explicit typed models (tte-engine: pydantic v2);
   response models list exactly the contract's fields, so nothing extra leaks.
3. Authorization first: resolve the caller and check the permission before any data access.
   Scope every query to the caller's tenant in the query itself, not by filtering afterwards.
   A cross-tenant id behaves as not found.
4. Respect the repository's data rules (tte-engine: "Profile, don't read" — admin surfaces never
   return memory or conversation content).
5. Lists: enforce the contract's page-size maximum and sort keys server-side; reject unknown
   sort keys and filters with the contract's error.
6. Migrations: follow the repository's mechanism (tte-engine: numbered SQL files in
   `src/contextbank/db/migrations/`, plus the documents its AGENTS.md names for a migration).
   Never destructive without an explicit decision in the spec.
7. Regenerate the committed contract with the repository's generator when the approved change
   adds to it (tte-engine: `uv run python scripts/export_openapi.py`; its `--check` runs in
   validation). Any other diff in it means the code drifted from the contract.
8. Tests beside the code (tte-engine: pytest): happy path, validation errors, permission denied,
   another tenant's id, pagination edges.
9. Commit, then `tte-harness evidence run` and `tte-harness evidence check` from the worktree root.

## Outputs

- Commits on the task branch: code, tests, migration, regenerated contract where approved, and
  the documents the repository requires for the kind of change.
- Evidence recorded in the run folder; a `worker_done` report.

## Validation

- The repository's whole validation sequence passes (tte-engine: `make lint`, `make test` with
  the test database, the OpenAPI check, `make audit`).
- The committed contract diff contains exactly the approved change and nothing else.
- Every new query is tenant-scoped; a test proves another tenant's data is not returned.

## Escalate when

- The contract cannot be implemented as written (missing data, impossible constraint).
- The change needs a new dependency, a destructive migration or a permission-model change.
- A validation step fails on the base branch too: report it; do not fix unrelated code.
