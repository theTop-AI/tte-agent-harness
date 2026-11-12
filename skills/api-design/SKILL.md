---
name: api-design
description: >-
  Use when an HTTP API between repositories must be defined or changed before implementation:
  endpoints, request and response schemas, errors, pagination, filtering, authorization and
  versioning, written as an api-contract.md a person approves and every worker then pins.
metadata:
  category: planning
  version: 1.0.0
---

# API design

A contract is the one thing two parallel workers in two repositories share. Design it so both
can build against it without talking to each other, and so a change to it is never silent.

## When to use

- A feature needs a new endpoint, or a change to one, consumed by another repository.
- A task brief or review finds the frontend and backend disagreeing about a payload.
- Not for an internal function signature inside one repository: that is ordinary design.

## Inputs

- The approved `requirements.md` (functional requirements, acceptance criteria, NFRs).
- The owner repository's existing API: read its router, schemas, error envelope, pagination and
  auth code, and its committed contract file if it has one (tte-engine: `openapi.json`, generated
  by `scripts/export_openapi.py`). Cite the files you read.
- The consumer repository's API client layer (tte-frontend: `packages/api-engine`).

## Procedure

1. Read how the owner repository already does each convention below; never invent a second style.
   Write down the file that shows each one.
2. For every endpoint fill the `templates/api-contract.md` sections: purpose, permission, request
   parameters with constraints and defaults, the full response schema with nullability, every
   error status with its machine-readable `code`, and one example request and response.
3. Lists: specify pagination (cursor or offset, as the owner already does), a hard maximum page
   size, the default and allowed sort keys, and each filter with its exact semantics.
4. Authorization and isolation: name the permission, and state that every query is scoped to the
   caller's tenant. List fields that must never be returned (secrets, other tenants' data,
   prompt or transcript content — the engine's "profile, don't read" rule).
5. Compatibility: say whether the change is additive. A removal or a type change is breaking and
   needs a new version and a migration note for every consumer.
6. Contract tests: name the server test that proves the implementation matches, and how each
   consumer gets fixtures or mocks from the same document. Detail: [contract tests](references/contract-checklist.md).
7. Set the version (`1.0.0` for a new contract; semver after) and status `draft`. Hand it to the
   person for approval; after approval, `tte-harness spec lock` pins it.

## Outputs

- `spec/api-contract.md` in the feature folder, status `draft`, ready for approval.
- A short list of open questions, if any, at its end — never resolved by guessing.

## Validation

- Every endpoint has request, response, errors and an example; every list has pagination limits.
- Each acceptance criterion that involves the API maps to at least one endpoint behaviour.
- Every convention cites the owner repository file it follows.
- The checklist in [references/contract-checklist.md](references/contract-checklist.md) passes.

## Escalate when

- The requirements need data the owner repository does not have, or a permission model it lacks.
- The only workable design breaks an existing consumer.
- A contract is already approved and implementation shows it is wrong: stop the affected tasks
  and ask the coordinator for a contract change; never patch the contract inside a task.
