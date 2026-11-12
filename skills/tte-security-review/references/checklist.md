# Security review checklist

Copy the applicable lines into the review report with yes / no / n.a. and evidence.

## Identity and access

- [ ] New routes require authentication through the repository's standard dependency/middleware.
- [ ] Permission checked server-side before any read or write; client-side hiding is not a check.
- [ ] Every query filters by the caller's tenant in SQL (or the ORM filter), not after loading.
- [ ] Object ids from the request are looked up within the caller's tenant only.
- [ ] Cross-tenant access returns not-found, with no timing or message difference worth noting.
- [ ] Admin or support bypasses are absent, or explicit, audited and covered by the spec.

## Input handling

- [ ] SQL uses bound parameters; no string formatting into queries.
- [ ] No `subprocess`/shell call built from request data; no `eval`/`exec`/`pickle` on input.
- [ ] Sizes bounded: string lengths, list lengths, page size, upload size.
- [ ] Output encoding: no raw HTML injection in React (`dangerouslySetInnerHTML`) without sanitising.
- [ ] Redirect targets and URLs from input are validated against an allow-list (open redirect, SSRF).

## Data exposure

- [ ] Response models list contract fields only; serialising whole ORM rows is a finding.
- [ ] Product-forbidden fields never appear (tte-engine: content, text, prompt, transcript, messages).
- [ ] Error responses carry codes and messages, not stack traces, SQL or internal hostnames.
- [ ] Logs carry no tokens, keys, personal data beyond what the repository already logs.

## Secrets and configuration

- [ ] No credential-shaped string in code, tests, fixtures, docs or commit messages.
- [ ] New configuration is read from the environment and documented in the env example file.
- [ ] Defaults are safe (secure cookies, auth enabled) outside explicit local modes.

## Dependencies and supply chain

- [ ] New dependencies are needed, maintained, pinned, and from the official registry.
- [ ] Lockfile changes match the manifest change and nothing else.
- [ ] No install scripts or network fetches added to build or test steps without a reason.

## Infrastructure boundary

- [ ] No IAM, network or production configuration changed from an application task.
- [ ] No migration that deletes or rewrites data without a spec decision and a backup plan.
