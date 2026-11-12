# plan.yaml rules

What `tte-harness plan --check` enforces (tte_harness/feature.py `validate_plan`), and the
conventions that make a plan run well in Orca.

## Enforced

| Rule | Why |
|---|---|
| `schema: 1`, `feature` lowercase-hyphenated, `workflow` is a folder under `workflows/` | the run folder and Orca objective are named from it |
| `spec` names a folder next to the plan, with `spec.lock.json` once approved | `tte-harness plan` refuses a spec that changed since its lock |
| every task has `id title role repo depends_on inputs outputs gates done_when status blockers` | the brief renders every one of them |
| `id` unique and lowercase-hyphenated | it becomes the Orca task title and the evidence folder |
| `role` is an agent; `repo` is in the registry; the role is in that repo's `roles` | e.g. no developer role writes to tte-infra in v1 |
| `depends_on` names existing tasks; no task depends on itself; no cycle | Orca creates tasks in dependency order |
| `inputs`, `outputs`, `done_when` are non-empty lists | a worker gets nothing else |
| each `inputs` entry is a spec file, optionally `#anchor` of one of its headings | the brief quotes exactly that section |
| `gates` are names from `config/quality-gates.yaml` | `evidence check` decides them |
| `review-pass` in `gates` needs `review_by` | the review is recorded against that task |
| a `review_by` task has role `code-reviewer` and depends on the task it reviews | a review cannot start before the work |
| `contract_change` is only `approved`, and only in a repo with `contract_paths` | everything else must leave the contract alone |
| `status` is a lifecycle state from `config/harness.yaml` (normally `PENDING`) | |

## Conventions

- Anchors are GitHub-style: lowercase, spaces become `-`, punctuation dropped
  (`## Functional requirements` is `#functional-requirements`).
- Name tasks `<side>-<what>`: `be-users-api`, `fe-users-tests`, `review-engine`.
- Wave 1 is usually every implementation and QA task; wave 2 the reviews; wave 3 integration.
- A task that needs a person before it starts carries `approval: "<question>"`; Orca opens a
  decision gate on it and the harness reports it as NEEDS_APPROVAL.

## Example waves

```text
wave 1: be-users-api, be-users-tests, fe-users-screen, fe-users-tests   (parallel)
wave 2: review-engine, review-frontend                                  (parallel)
wave 3: integration                                                     (approval gate)
```
