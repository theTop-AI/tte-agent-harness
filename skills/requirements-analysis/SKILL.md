---
name: requirements-analysis
description: >-
  Use when a feature request, ticket or idea must become testable requirements before design:
  business context, numbered functional and non-functional requirements, Given/When/Then
  acceptance criteria, scope, dependencies and risks, written as spec/requirements.md.
metadata:
  category: planning
  version: "1.0.0"
---

# Requirements analysis

Turn what someone asked for into requirements a tester can check and an architect can design
against, without deciding the design. Every later artifact points back to these ids.

## When to use

- A feature, ticket or request arrives and no approved `requirements.md` exists for it yet.
- An existing requirement is vague enough that two workers would build different things.
- Not for designing components or APIs: that is `solution-architecture` and `api-design`.

## Inputs

- The request in its original words (ticket text, message, document), quoted, never paraphrased.
- The product context of each affected repository: its `AGENTS.md`, product notes (tte-frontend:
  `apps/web/PRODUCT.md`; tte-engine: `docs/`), and the living specs under `docs/specs/` if any.
- What exists today: the screens, endpoints or jobs the request touches, read in the code.

## Procedure

1. Copy the request word for word into the Business context section, then state in two short
   paragraphs who needs it, the problem it removes, and how anyone will know it worked.
2. Read the current behaviour in each affected repository and name the files you read. A
   requirement that already holds is not a requirement; one that contradicts a recorded decision
   (an ADR, a living spec) is an open question.
3. Write functional requirements as `FR-n — The system SHALL ...`: one behaviour each, observable
   from outside, no implementation words (no table names, no component names).
4. Write non-functional requirements with a number or a named standard: performance (p95, size),
   security (who may see what, tenant isolation, data never returned), accessibility, freshness.
5. Write acceptance criteria as `AC-n (FR-m) — Given ..., when ..., then ...`. Cover the happy
   path, the empty state, invalid input, a caller without permission, and another tenant's data.
6. Fill Out of scope, Dependencies (per repository), Known risks and Definition of Done from
   `templates/requirements.md` in the harness checkout.
7. List open questions at the end. Never resolve one by guessing; it goes to the person who owns
   the request.

## Outputs

- `spec/requirements.md` in the feature folder, status `draft`, in the template's shape.
- A list of open questions for the request owner, if any.

## Validation

- Every sentence of the original request maps to at least one FR or to Out of scope.
- Every FR has at least one AC; every AC names its FR and is observable without reading code.
- No requirement names an implementation detail; every NFR has a measurable bound.
- Authorization and tenant isolation are stated explicitly for any data the feature shows.

## Escalate when

- The request is ambiguous on who the user is, what they may see, or what "done" means.
- It conflicts with an ADR, a living spec, or a product rule of an affected repository.
- It needs a repository, team or release outside the ones the request names.
