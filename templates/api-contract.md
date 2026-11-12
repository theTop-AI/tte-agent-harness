# <Feature title> — API contract

Contract: `<name>` · Version: `1.0.0` · Owner repository: `<backend repo>` ·
Consumers: `<frontend repo>` · Status: draft | approved

The approved version of this file is pinned by the spec lock. Any change after approval is a new
version, a new lock and a new approval; no worker changes it on its own.

## Conventions

Base path, authentication, content type, error envelope, pagination and filtering style — the
ones the owner repository already uses (cite the file that shows it).

## Endpoints

### `<METHOD> <path>`

Purpose in one sentence. Required permission.

**Request** — parameters table: name, in (path/query/body), type, required, constraints, default.

**Response 200** — schema with every field, its type and whether it can be null.

**Errors** — status, `code`, when it happens.

**Example**

```http
GET /api/v1/... HTTP/1.1
```

```json
{}
```

## Compatibility

What existing clients see; whether the change is additive; deprecations.

## Contract tests

Which tests in the owner repository prove the server honours this contract, and which tests in
each consumer prove it reads it correctly (fixtures or mocks generated from this file).

## Change process

1. Propose the change to the coordinator; the work that needs it stops.
2. The architect revises this file and bumps the version.
3. A person approves; `tte-harness spec lock` pins the new digest; affected tasks restart.
