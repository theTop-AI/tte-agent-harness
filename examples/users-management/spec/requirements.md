# Users management — requirements

Feature id: `users-management` · Ticket: none (illustrative) · Author: solution-architect ·
Status: approved (example only)

> **Illustrative example.** This feature is not a real ticket. The repositories, files and
> conventions it cites are real as of 2026-11-12 (`theTop-AI/tte-engine` and
> `theTop-AI/tte-frontend` at `origin/main`), so the example exercises the harness on the shapes a
> real feature meets. Nothing here was implemented, and the approval recorded in `spec.lock.json`
> is not a person's approval.

## Business context

An organization's administrators need to see who can sign in to the panel and with which panel
role, to answer "who has access to our AI spend data?" without opening WorkOS. Today the panel
shows people who *use* AI tools (the People screen, `GET /api/v1/identity/principals`), not the
panel's own members and their roles.

Success: an administrator finds any member by name or email and sees their role and last sign-in
in under ten seconds, on an organization of 5 000 members.

## Functional requirements

- **FR-1** — The engine SHALL list the panel members of the caller's organization, one row per
  member: id, display name, email, panel role, status, created and last sign-in timestamps.
- **FR-2** — The list SHALL be searchable by a case-insensitive substring of display name or email.
- **FR-3** — The list SHALL be filterable by panel role (`admin`, `member`, `viewer`) and status
  (`active`, `invited`, `disabled`).
- **FR-4** — The list SHALL be sortable by name (default) or last sign-in, and paged with an opaque
  cursor.
- **FR-5** — The panel SHALL show a Users screen with the list, the search box, the role filter,
  and "Load more" paging, plus loading, empty, error and freshness states.

## Non-functional requirements

- **NFR-1 Performance** — the first page answers in under 300 ms at p95 for 5 000 members.
- **NFR-2 Security** — only an organization administrator may call the endpoint; every query is
  scoped to the caller's organization; no response carries credentials, keys, tokens, or any
  content field (`content`, `text`, `prompt`, `transcript`, `messages`).
- **NFR-3 Accessibility** — the screen is keyboard-operable end to end and meets WCAG 2.2 AA.
- **NFR-4 Freshness** — the screen states how fresh the list is from `meta.freshness`, never from a
  client clock.

## Acceptance criteria

- **AC-1 (FR-1)** — Given an admin of org A with 3 members, when the Users screen opens, then the 3
  members appear with name, email, role, status and last sign-in.
- **AC-2 (FR-2)** — Given members "Ada Lovelace" and "Alan Turing", when the admin searches "ada",
  then only Ada Lovelace is listed.
- **AC-3 (FR-3)** — Given admins and viewers, when the admin filters role = viewer, then only viewers
  are listed and the filter is reflected in the URL.
- **AC-4 (FR-4)** — Given 120 members and a page size of 50, when the admin loads more twice, then
  all 120 appear once each, in order, and no "Load more" remains.
- **AC-5 (NFR-2)** — Given a non-admin caller, when the endpoint is called, then it answers 403
  `forbidden`; given a member id of org B, it never appears in org A's list.
- **AC-6 (FR-5)** — Given no member matches the search, then the screen shows the empty state with a
  way to clear the search; given the engine fails, the error state offers a retry.
- **AC-7 (NFR-4)** — Given `meta.freshness.state = stale`, then the screen says the list may be out
  of date.

## Out of scope

Inviting, disabling or changing the role of a member (a follow-up; Policies remains the single edit
surface). The People screen and `/identity/principals` stay as they are.

## Dependencies

- tte-engine: the WorkOS membership data the engine already reads for `require_admin`.
- tte-frontend: the pinned contract in `packages/api-engine/contract/` moves to the engine release
  that carries the endpoint (tte-frontend ADR-0001) — the integration step, not a worker's choice.

## Known risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Overlap with People / principals confuses users | Medium | Medium | Name the screen "Users" with a one-line explanation; architect records the distinction |
| Membership data lags WorkOS | Medium | Low | Freshness state from `meta.freshness` |
| Search on 5 000 rows is slow | Low | Medium | Index on lower(display_name), lower(email) |

## Definition of Done

- Every AC has a passing automated test (unit, API or e2e) on the pull request head.
- Every task of `plan.yaml` passed `tte-harness evidence check`.
- Pull requests in tte-engine and tte-frontend are open with green CI; a person approved each merge.
- A living spec `docs/specs/users.md` is added in each repository in the same pull request as the
  behaviour (tte-workflows living specs).
