# <Feature title> — requirements

Feature id: `<feature-id>` · Ticket: TTE-<n> · Author: <role/person> · Status: draft | approved

## Business context

Who needs this, the problem it removes, and how we will know it worked. Two short paragraphs.

## Functional requirements

Each requirement is testable and numbered; acceptance criteria refer to these ids.

- **FR-1** — <The system SHALL ...>
- **FR-2** — <...>

## Non-functional requirements

- **NFR-1 Performance** — <e.g. the list returns in < 300 ms at p95 for 10 000 rows>
- **NFR-2 Security** — <authorization rule, tenant isolation, data that must never be returned>
- **NFR-3 Accessibility** — <WCAG level, keyboard path>

## Acceptance criteria

Given/When/Then, one per behaviour, each naming the requirement it proves.

- **AC-1 (FR-1)** — Given <state>, when <action>, then <observable result>.

## Out of scope

What a reader might expect here but this feature does not do, and where it goes instead.

## Dependencies

Other features, tickets, releases or teams this needs, and which repository each touches.

## Known risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|

## Definition of Done

- Every AC has a passing automated test, or a named manual check where none can observe it.
- Every task of the plan passed `tte-harness evidence check`.
- Pull requests open with green CI; a person approved each merge.
- Living specs (`docs/specs/<capability>.md`) updated in the same pull request as the behaviour.
