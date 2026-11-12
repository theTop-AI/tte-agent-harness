---
name: solution-architecture
description: >-
  Use when approved requirements need a design before implementation: investigate the existing
  code of each affected repository, define components, interfaces, data and decisions, name
  risks and the delivery shape, written as spec/architecture.md for a person to approve.
metadata:
  category: planning
  version: "1.0.0"
---

# Solution architecture

Design the smallest change that meets the requirements in the code as it is, decided explicitly
enough that parallel workers in different repositories cannot drift apart.

## When to use

- `requirements.md` is written and the feature touches more than one file's worth of design.
- A worker or reviewer reports that the design leaves a decision open.
- Not for writing endpoint schemas (`api-design`) or the task graph (`task-decomposition`).

## Inputs

- The approved or draft `spec/requirements.md`.
- Each affected repository at its base branch: `AGENTS.md`, architecture docs (tte-frontend:
  `docs/architecture/apps-web.md`, `docs/adr/`; tte-engine: `docs/system/ARCHITECTURE.md`),
  and the modules the change will touch.
- The harness repository registry (`tte-harness repos`) for paths, roles and contract paths.

## Procedure

1. Investigate before proposing. For each repository, read the entry points the feature reaches
   (routes, handlers, data access, client layer) and write down what exists, with file paths.
2. Choose the design that reuses existing patterns. If a pattern is missing, propose it once and
   say why the existing ones do not fit.
3. Fill `templates/architecture.md`: context, components table (repository, new or changed,
   responsibility), interfaces, data with tenant scoping, decisions with the options weighed.
4. Interfaces between repositories go through a contract: hand the endpoint detail to
   `api-design` and reference `api-contract.md`; never let a design depend on two repositories
   agreeing informally.
5. Security and isolation: who is authenticated how, which permission each operation needs,
   how every query is scoped to the caller's tenant, what is never returned.
6. Failure modes: for each dependency, what happens when it is slow, down or wrong, and what
   the user sees.
7. Delivery shape: name the units that can be built independently once the contract is fixed,
   the integration point, and what must wait. `task-decomposition` turns this into `plan.yaml`.
8. Record a decision that changes an existing ADR as such, and name the ADR.

## Outputs

- `spec/architecture.md`, status `draft`, with every decision numbered (`D1`, `D2`, ...).
- `spec/test-plan.md` started from `templates/test-plan.md` with the levels each risk needs.
- Open questions and the risks table.

## Validation

- Every FR and NFR is served by a named component or decision.
- Every cross-repository interaction is covered by the API contract.
- Every claim about existing code cites a file that exists at the base branch.
- No decision is left to "the implementer will decide" where two tasks depend on it.

## Escalate when

- The requirements cannot be met without a breaking change to a contract other consumers use.
- The design needs infrastructure changes (tte-infra) or privileged operations: those stay with
  a person in v1.
- Two reasonable designs differ in cost or risk enough that the person should choose.
