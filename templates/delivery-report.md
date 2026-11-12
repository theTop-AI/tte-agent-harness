# <Feature title> — delivery report

Feature id: `<feature-id>` · Spec: `<sha256 digest>` · Orca Run: `<run id>` · Date: <YYYY-MM-DD>

## Outcome

One paragraph: what was delivered, what was not, and what a person must decide now.

## Tasks

| Task | Role | Repository | State | Evidence (`tte-harness evidence check`) | Pull request |
|---|---|---|---|---|---|

States are the harness lifecycle (`tte-harness status`), never an agent's own word.

## Acceptance criteria

| AC | Verified by | Result |
|---|---|---|

## Pull requests and CI

| Pull request | Head commit | CI on head | Review | Ready to merge? |
|---|---|---|---|---|

## Contract

The contract version every repository implements, and confirmation that no worker changed it
outside an approved change.

## Open findings and risks

Every unresolved review finding, failed or skipped check, and known risk, with an owner.

## Decisions needed from a person

- Merge approvals, in order (name the dependency order across repositories).
- Anything else that blocks release.
