# Release validation

Proves a release candidate is consistent across repositories before a person releases it. It
reads, runs checks and reports; it never deploys, tags, merges or applies infrastructure.
[workflow.yaml](workflow.yaml) is the checked version of this page.

## Stages

| # | Stage | Role | Waits for | Gates |
|---|---|---|---|---|
| 1 | candidate | integration-engineer | — | — |
| 2 | contract-check | integration-engineer | 1 | — (findings go to the report) |
| 2 | repo-validation (per repository) | integration-engineer | 1 | `repo-validate`, `clean-commit`, `no-secrets` |
| 2 | security-review (per repository) | code-reviewer | 1 | `security-reviewed` |
| 3 | ci (per repository) | integration-engineer | contract-check, repo-validation | `pr-created`, `ci-green` |
| 4 | report | coordinator, then **person** | ci, security-review | `acceptance-verified`, `risks-documented`, `human-merge-approval` |

## Step by step

1. **Candidate.** Write `spec/release-candidate.md`: for each repository the release pull request
   (release-please opens `chore(main): release X.Y.Z`), its head commit, and the version it will
   produce. Lock it with `tte-harness spec lock`; the heads are now the thing being validated.
2. **Contract check.** The engine serves the contract the frontend vendors. Compare tte-frontend
   `packages/api-engine/contract/VERSION` (and its `*_SHA256` files) with the tte-engine release
   that will serve it, and the engine's committed `openapi.json` at that release. A mismatch is a
   blocking finding, never something to patch during validation.
3. **Repository validation.** In a worktree at each release head, `tte-harness evidence run`
   runs the repository's own validation sequence from its `.claude/project.json`.
4. **Security review.** A `code-reviewer` worker reviews the diff since the previous release with
   the tte-security-review skill and records the verdict with `tte-harness evidence review`.
5. **CI.** `tte-harness evidence pr --pr <release PR>` records each release pull request and
   the checks GitHub reports on its head; `ci-green` passes only when all of them passed.
6. **Report.** The coordinator's report lists each repository's version, head, validation, CI,
   contract comparison, security verdict and open risks, and the order to release in. Its Orca
   decision gate asks the person for a go or no-go.

## Where Orca does what

Orca runs one worker per repository and stage, in worktrees at the release heads, and holds the
final decision gate. The harness pins the candidate and records the evidence.

## Human only

- Merging release pull requests; releases are never cut by hand (`git tag`) or by an agent.
- Deploys: tte-infra applies `tte-dev` on merge to its `main`, and tenants move only on engine
  releases, by hand (`deploy-release.yml`). No agent runs `terraform apply` or a deploy workflow.
- Any privileged AWS operation.
