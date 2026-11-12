# Users management — API contract

Contract: `users-api` · Version: `1.0.0` · Owner repository: `tte-engine` ·
Consumers: `tte-frontend` · Status: approved (example only)

The approved version of this file is pinned by `spec.lock.json`. Any change after approval is a new
version, a new lock and a new approval; no worker changes it on its own.

## Conventions

Followed from the owner repository, `origin/main` 2026-11-12:

- Base path `/api/v1` (`src/contextbank/server/api/__init__.py`, `API_PREFIX`).
- Authentication: the caller's own access token or admin key; the route depends on `require_admin`
  (`server/api/deps.py`).
- Success payload: `Envelope` — `{"data": ..., "meta": {..., "freshness": {...}, "generated_at"}}`
  (`server/api/schemas.py`).
- Errors: `{"error": {"code", "message", "param"}}` with codes `bad_param` (400), `unauthorized`
  (401), `forbidden` (403), `not_found` (404) (`server/api/errors.py`).
- Paging: opaque keyset `cursor`, `limit` 1–200 default 50, `next_cursor` only on a full page, a
  foreign cursor is 400 `bad_param` (`server/api/identity.py`, `/identity/principals`).

## Endpoint: list users

`GET /api/v1/users` — the panel members of the caller's organization. Permission: organization
administrator (`require_admin`).

### Request

| Name | In | Type | Required | Constraints | Default |
|---|---|---|---|---|---|
| `q` | query | string | no | 1–200 chars; case-insensitive substring of display name or email | — |
| `role` | query | enum | no | `admin` \| `member` \| `viewer` | all |
| `status` | query | enum | no | `active` \| `invited` \| `disabled` | all |
| `sort` | query | enum | no | `name` \| `last_sign_in` | `name` |
| `cursor` | query | string | no | the `next_cursor` of the previous page, unchanged | — |
| `limit` | query | integer | no | 1–200 | 50 |

Order: `name` sorts by `lower(coalesce(display_name, email)), id` ascending; `last_sign_in` by
`last_sign_in_at desc nulls last, id`.

### Response 200

`Envelope[Users]`:

| Field | Type | Null | Meaning |
|---|---|---|---|
| `data.rows[].id` | string (uuid) | no | member id, stable |
| `data.rows[].display_name` | string | yes | as WorkOS holds it |
| `data.rows[].email` | string | no | sign-in address |
| `data.rows[].role` | enum `admin` \| `member` \| `viewer` | no | panel role |
| `data.rows[].status` | enum `active` \| `invited` \| `disabled` | no | membership state |
| `data.rows[].created_at` | string (ISO 8601 UTC) | no | membership created |
| `data.rows[].last_sign_in_at` | string (ISO 8601 UTC) | yes | null when never signed in |
| `data.total` | integer | no | members matching the filters, across all pages |
| `data.next_cursor` | string | yes | null on the last page |
| `meta.freshness.state` | enum (engine `EnvelopeState`) | no | how current the membership mirror is |
| `meta.freshness.as_of` | string (ISO 8601 UTC) | yes | when the mirror was last read |

No field carries a credential, a key, a token, or content (`content`, `text`, `prompt`,
`transcript`, `messages`).

### Errors

| Status | `code` | When |
|---|---|---|
| 400 | `bad_param` | an unknown `role`/`status`/`sort`, `limit` out of range, `q` too long, a cursor this route did not issue (`param` names the field) |
| 401 | `unauthorized` | no or invalid credential |
| 403 | `forbidden` | the caller is not an organization administrator |

An empty match is 200 with `rows: []` and `total: 0`, never 404.

### Example

```http
GET /api/v1/users?q=ada&role=admin&limit=2 HTTP/1.1
Authorization: Bearer <session access token>
```

```json
{
  "data": {
    "rows": [
      {
        "id": "4f6c1d2a-6b7e-4f43-9a8e-0c1d2e3f4a5b",
        "display_name": "Ada Lovelace",
        "email": "ada@example.com",
        "role": "admin",
        "status": "active",
        "created_at": "2026-09-01T08:00:00Z",
        "last_sign_in_at": "2026-11-11T17:42:10Z"
      }
    ],
    "total": 1,
    "next_cursor": null
  },
  "meta": {
    "freshness": { "state": "live", "as_of": "2026-11-12T09:00:00Z", "sources": [], "revised": false, "reason": null },
    "scope": "org",
    "generated_at": "2026-11-12T09:00:01Z"
  }
}
```

## Compatibility

Additive: a new operation; no existing operation or schema changes. The frontend picks it up by
moving its pinned contract (`packages/api-engine/contract/VERSION`) to the engine release that
carries it.

## Contract tests

- tte-engine: `scripts/export_openapi.py --check` (the committed `openapi.json` matches the routers)
  plus route tests for every row of the Errors table and for tenant scoping.
- tte-frontend: the generated zod model parses the example above; the mock engine answers the
  operation from fixtures generated from the same `openapi.json`, so e2e specs read the contract,
  not a hand-written copy.

## Change process

1. A worker that needs a change stops and asks the coordinator (`orca orchestration ask`).
2. The architect revises this file and bumps the version.
3. A person approves; `tte-harness spec lock` pins the new digest; affected tasks restart from the
   new briefs.
