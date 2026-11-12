# API test matrix

For each endpoint, one test (or one parametrised case) per row that applies.

| Area | Case | Expected |
|---|---|---|
| contract | success response | status, every field with type and nullability, no extra field |
| contract | example from the contract | the documented example request returns the documented shape |
| authentication | no credentials | 401 with the contract's error code |
| authorization | authenticated, without the permission | 403 (or the contract's choice) |
| isolation | another tenant's existing id | 404, no data, nothing that confirms existence |
| isolation | list as tenant A | no row of tenant B, even when B has more data |
| validation | missing required field, wrong type, value out of range | 400/422 with `code` per field |
| validation | over-long strings, unknown enum values | rejected, not truncated |
| pagination | first, middle and last page; empty list | correct items, stable order, `200` on empty |
| pagination | page size at the maximum and above it | maximum honoured; above it rejected or clamped as the contract says |
| filtering | each filter alone and combined; unknown filter | exact semantics; unknown is an error |
| sorting | each sort key, both directions; unknown key | stable order; unknown is an error |
| errors | dependency down or slow (where testable) | the contract's 5xx shape, no stack trace |
| data rules | fields the product forbids (tte-engine: content, text, prompt, transcript, messages) | never present |
| regression | the defect that prompted the change | stays fixed |

## Coverage gaps

A gap is any row that applies but has no test. List each with the reason and who decides
whether it may stay open.
