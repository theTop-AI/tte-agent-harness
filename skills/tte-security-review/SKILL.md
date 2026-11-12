---
name: tte-security-review
description: >-
  Use when a diff or design must be checked for security: authentication, authorization, tenant
  isolation, injection, secrets, SSRF, unsafe deserialization, dependency risk and data
  exposure, with each finding tied to file:line and an exploit scenario.
metadata:
  category: quality
  version: "1.0.0"
---

# Security review (harness)

Named `tte-security-review` because Claude Code bundles its own `/security-review`; this one is
the checklist a harness reviewer applies to a task's diff and attests as `security-reviewed`.

Assume every input is hostile and every caller is from another tenant until the code proves
otherwise.

## When to use

- Inside a `tte-code-review` of any task that touches routes, queries, auth, files, HTTP calls,
  dependencies or configuration.
- When an architecture proposes a new data flow, identity or external call.
- Not a replacement for the repository's own security tooling; run that too (tte-engine:
  `make audit`).

## Inputs

- The diff against the merge-base, and the files it calls into.
- The pinned spec's security and isolation sections and the API contract.
- The repository's security docs (tte-engine: `docs/system/SECURITY.md`,
  `docs/system/AUTHENTICATION.md`).

## Procedure

Walk [the checklist](references/checklist.md) over the diff. For each area that applies:

1. Authentication: every new route requires the repository's auth; no debug bypass, no default
   credentials.
2. Authorization: the permission check runs before data access, server-side, on every path,
   including list and export variants.
3. Tenant isolation: tenant scoping lives in the query; ids from the request are never trusted
   to imply tenancy; a cross-tenant id behaves as not found.
4. Injection: SQL through parameters only; no shell with request data; templates escape output;
   no `eval`; React output not built with raw HTML.
5. Secrets: none in code, tests, fixtures or logs; config read from the environment; the diff
   passes the `no-secrets` gate.
6. SSRF and outbound calls: URLs from input are allow-listed; timeouts on every call.
7. Data exposure: responses carry only contract fields; product-forbidden fields never appear
   (tte-engine "Profile, don't read": no memory or conversation content on admin surfaces);
   errors carry no stack traces or internal ids.
8. Dependencies: new packages are pinned, maintained and needed; the lockfile changes match.
9. For each finding write: file:line, the attack (who sends what), the impact, the fix.

## Outputs

- Security findings inside the review report, severity critical for any authorization,
  isolation, injection or secret defect.
- The `security-reviewed` gate attested in `tte-harness evidence review --attest` only when the
  whole checklist was applied.

## Validation

- Every applicable checklist area has a line in the report, even when it found nothing.
- Every finding has an exploit scenario a person can reproduce or reason through.

## Escalate when

- A credential is in the diff or its history: stop, tell the coordinator and the person; the
  secret must be rotated, not just removed.
- The design itself is unsafe (the fix is a spec change, not a code change).
- The change touches infrastructure, IAM or production data paths: a person reviews it too.
