# <Feature title> — architecture

Feature id: `<feature-id>` · Requirements: `requirements.md` · Status: draft | approved

## Context

What exists today in each affected repository (with file paths you read), and what this design
changes. Name every repository the feature touches.

## Components

| Component | Repository | New or changed | Responsibility |
|---|---|---|---|

## Interfaces

The contracts between components. API endpoints are specified in `api-contract.md`; describe
here only how components use them (who calls what, when, with which identity).

## Data

Entities, ownership, migrations, retention. State tenant scoping explicitly.

## Decisions

Each decision with the options considered and why this one. A decision that changes a recorded
ADR names that ADR.

- **D1** — <decision> · Options: <a>, <b> · Because: <reason>

## Security and isolation

Authentication, authorization, tenant isolation, data never returned, audit.

## Failure modes

What happens when each dependency is slow, down or returns an error, and what the user sees.

## Delivery shape

How the work splits into independently executable tasks (detailed in `../plan.yaml`), what can
run in parallel, and what must wait for what. Name the integration point.

## Risks

| Risk | Mitigation | Owner |
|---|---|---|
