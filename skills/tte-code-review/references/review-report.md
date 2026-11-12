# Review report format

Save as a Markdown file and pass it to `tte-harness evidence review --findings <file>`.

```markdown
# Review of <task-id> at <commit>

Spec: <sha256 digest> · Reviewer: <session or dispatch id> · Verdict: pass | fail

## Summary

Two or three sentences: what the change does, whether it does what the brief asks, and the
reason for the verdict.

## Findings

### C1 — critical — <one-line title>

`path/to/file.py:120-134` — what is wrong, what the spec or rule says, the failing input or
scenario, and the smallest fix that would resolve it.

### M1 — major — <title>
...

### m1 — minor — <title>
...

### n1 — nit — <title>
...

## Gates checked

- scope-matches-task: yes/no — <why>
- security-reviewed: yes/no — <what was checked>
- tests-cover-criteria: yes/no — <AC ids without a test, if any>

## Not reviewed

Anything outside what you could judge, and why.
```

Severity guide:

| Severity | Examples | Blocks pass? |
|---|---|---|
| critical | wrong behaviour against an AC, authorization or tenant-isolation hole, unapproved contract change, data loss, secret committed | yes |
| major | AC without a test, scope creep into another task, broken repository convention, missing error handling | no, but the coordinator decides before integration |
| minor | naming, small duplication, unclear comment | no |
| nit | style the linter does not catch | no |
