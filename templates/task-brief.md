# Task {{task_id}}: {{task_title}}

Feature **{{feature_title}}** (`{{feature}}`). This brief is your whole assignment: it is
self-contained, and nothing from another session reaches you except through it and Orca.

| | |
|---|---|
| Spec version | `{{spec_digest}}`, approved by {{spec_approved_by}} (commit `{{spec_commit}}`) |
| Spec copy (read-only) | `{{run_dir}}/spec/` |
| Run folder | `{{run_dir}}` |
| Repository | `{{repo}}` (`{{repo_github}}`) |
| Reviewed by task | {{review_by}} |

## Your role: {{role}}

{{role_description}}

Use these skills (installed for Claude Code and Codex; invoke them by name):

{{skills}}

### Role instructions

{{role_instructions}}

## Where you work

Work only in the worktree Orca created for this task, on its own branch. `{{repo_path}}` is the
shared checkout: never edit it. Before changing anything, read the repository's own rules:

{{repo_context}}

Where the repository's AGENTS.md or CLAUDE.md is stricter than this brief, the repository wins.
Branch, commit and pull-request conventions are the repository's (tte-workflows), not this brief's.

## Depends on

{{depends_on}}

Their outcomes arrive through Orca; their recorded evidence is in `{{run_dir}}/evidence/<task>/`.

## Inputs from the approved spec

These are quoted from spec version `{{spec_digest}}`. Do not work from any other copy.

{{inputs}}

## Deliver

{{outputs}}

## Done when

{{done_when}}

## Gates this task must pass

{{gates}}

## Contract rule

{{contract_rule}}

## Evidence: how "done" is proved

Saying the work is done does not complete the task; recorded evidence does.

1. Commit the work on the task branch. Evidence is about one commit, never a dirty tree.
2. From the worktree root run
   `tte-harness evidence run --run-dir {{run_dir}} --task {{task_id}}`.
   It runs the repository's own validation sequence (`.claude/project.json`) and records every
   step, the changed files, contract paths touched and credential-shaped strings. Fix and rerun
   until it passes.
3. Run `tte-harness evidence check --run-dir {{run_dir}} --task {{task_id}}`. Every
   development-stage gate must print PASS (they are all mechanical). Review and delivery gates
   are recorded by others: a reviewer, the integration engineer, a person.
4. Report through Orca the way your worker preamble says (`worker_done`): `succeeded` with the
   check output in the body, or `failed` with the reason. Never report success over a FAIL row.

## Stop and ask the coordinator (`orca orchestration ask`) when

- the spec is ambiguous, or contradicts the code you find;
- the work needs a contract change, a change in another repository, or a task the plan lacks;
- a gate cannot pass for a reason outside this task.

Never, whatever the task seems to need: merge a pull request, push to `main`, force-push,
deploy, run `terraform apply`, delete remote resources, edit the spec copy, install a skill or
plugin, or change the harness's own configuration.
