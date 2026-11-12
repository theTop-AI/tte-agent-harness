# API contract checklist

Run through this before handing a contract for approval. Every "no" is either fixed or written
down as an open question at the end of the contract.

## Shape

- [ ] Every endpoint names method, path, purpose and required permission.
- [ ] Every request parameter has type, location, required/optional, constraints and default.
- [ ] Every response field has type and nullability; enums list every value.
- [ ] Timestamps are ISO 8601 UTC strings; money and counts state their unit.
- [ ] Errors use the owner's existing envelope and each has a stable machine-readable `code`.

## Lists

- [ ] Pagination style matches the owner repository; page size has a default and a maximum.
- [ ] Sort keys and their default order are listed; unknown sort keys are a 400, not ignored.
- [ ] Each filter states exact semantics (equality, prefix, case sensitivity, multi-value).
- [ ] An empty result is `200` with an empty list, never `404`.

## Security

- [ ] Every query is scoped to the caller's tenant; a cross-tenant id returns `404`, not `403`,
      so existence does not leak.
- [ ] No field returns secrets, credentials, or content the product rule forbids
      (`content`, `text`, `prompt`, `transcript`, `messages` in tte-engine).
- [ ] Input limits stop abuse: maximum lengths, maximum page size, rate limits where they exist.

## Compatibility and tests

- [ ] The change is additive, or it is versioned with a migration note per consumer.
- [ ] The server-side contract test is named (tte-engine: `scripts/export_openapi.py --check`
      plus the route tests).
- [ ] Each consumer's fixtures or mocks come from this document, not from a hand-written copy.
