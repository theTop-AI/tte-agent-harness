#!/usr/bin/env bash
# Simulate the users-management lifecycle end to end, with nothing real touched:
#   - two throwaway git repositories stand in for tte-engine and tte-frontend;
#   - a temporary repositories file points the harness at them (TTE_HARNESS_REPOSITORIES);
#   - Orca is replaced by a recorded task-list response, and stub `orca` and `gh` commands on PATH
#     make the run fail if anything tries to call the real ones;
#   - no network, no install, nothing outside one temporary folder, removed on exit.
#
#   examples/users-management/simulate.sh          run it
#   KEEP=1 examples/users-management/simulate.sh   keep the temporary folder for a look
#
# Exits non-zero on anything unexpected. Bash 3.2 compatible (macOS /bin/bash).
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
th="$root/bin/tte-harness"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/tte-harness-sim.XXXXXX")"

cleanup() {
  if [ "${KEEP:-0}" = 1 ]; then
    echo "kept $tmp"
    return
  fi
  chmod -R u+w "$tmp" 2>/dev/null || true
  rm -rf "$tmp"
}
trap cleanup EXIT

step() { printf '\n=== %s\n' "$*"; }
expect_fail() {
  # Run a command that must fail; a success is itself a failure of the simulation.
  if "$@"; then
    echo "UNEXPECTED: '$*' passed but should have failed" >&2
    exit 1
  fi
}

# Nothing may reach the real Orca or GitHub.
mkdir -p "$tmp/stub-bin"
for exe in orca orca-ide gh; do
  printf '#!/bin/sh\necho "simulate.sh: %s must not be called" >&2\nexit 99\n' "$exe" >"$tmp/stub-bin/$exe"
  chmod +x "$tmp/stub-bin/$exe"
done
export PATH="$tmp/stub-bin:$PATH"
unset ORCA_CLI_COMMAND ORCA_TERMINAL_HANDLE ORCA_WORKTREE_ID 2>/dev/null || true
export XDG_STATE_HOME="$tmp/state"

# Throwaway repositories: no global git config, hooks or signing from the person running this.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME="sim" GIT_AUTHOR_EMAIL="sim@example.invalid"
export GIT_COMMITTER_NAME="sim" GIT_COMMITTER_EMAIL="sim@example.invalid"

# make_repo <name>: a repository on main with a committed .claude/project.json whose validation
# sequence is two cheap shell checks, the shape tte-workflows repositories commit.
make_repo() {
  local dir="$tmp/repos/$1"
  mkdir -p "$dir/.claude" "$dir/src" "$dir/tests"
  cat >"$dir/.claude/project.json" <<'JSON'
{
  "name": "REPO",
  "baseBranch": "main",
  "validate": [
    {"name": "lint", "run": "! grep -rn FIXME src"},
    {"name": "tests", "run": "sh tests/run.sh"}
  ]
}
JSON
  sed -i.bak "s/REPO/$1/" "$dir/.claude/project.json" && rm "$dir/.claude/project.json.bak"
  # The generated script must keep "$f" literal, so single quotes are intended here.
  # shellcheck disable=SC2016
  printf '#!/bin/sh\n# every file under src/ must be non-empty\nfor f in src/*; do test -s "$f" || exit 1; done\n' >"$dir/tests/run.sh"
  echo "existing code" >"$dir/src/app.txt"
  git -C "$dir" init -q -b main
  git -C "$dir" add -A
  git -C "$dir" commit -q -m "chore: initial"
}

step "1. Two throwaway repositories and a repositories file pointing at them"
make_repo tte-engine
make_repo tte-frontend
echo '{"openapi": "3.1.0", "paths": {}}' >"$tmp/repos/tte-engine/openapi.json"
mkdir -p "$tmp/repos/tte-frontend/packages/api-engine/contract"
echo "v1.0.0" >"$tmp/repos/tte-frontend/packages/api-engine/contract/VERSION"
git -C "$tmp/repos/tte-engine" add -A && git -C "$tmp/repos/tte-engine" commit -q -m "chore: contract"
git -C "$tmp/repos/tte-frontend" add -A && git -C "$tmp/repos/tte-frontend" commit -q -m "chore: contract"
cat >"$tmp/repositories.yaml" <<YAML
schema: 1
repositories:
  tte-engine:
    github: theTop-AI/tte-engine
    path: $tmp/repos/tte-engine
    kind: backend
    context: [AGENTS.md]
    contract_paths: [openapi.json]
    roles: [solution-architect, backend-developer, backend-qa, code-reviewer, integration-engineer]
  tte-frontend:
    github: theTop-AI/tte-frontend
    path: $tmp/repos/tte-frontend
    kind: frontend
    context: [AGENTS.md]
    contract_paths: [packages/api-engine/contract/]
    roles: [solution-architect, frontend-developer, frontend-qa, code-reviewer, integration-engineer]
YAML
export TTE_HARNESS_REPOSITORIES="$tmp/repositories.yaml"
echo "repositories: $TTE_HARNESS_REPOSITORIES"

run="$tmp/run"
step "2. The approved spec matches its lock"
"$th" spec verify "$here/spec"

step "3. Plan: validate the DAG, copy the pinned spec, write one brief per task"
"$th" plan "$here/plan.yaml" --run-dir "$run"
ls "$run/briefs"

step "4. The Orca calls that would create the Run (printed, not executed)"
"$th" orca commands --run-dir "$run"

# A fake Orca: the id map `orca create` would write, and task-list snapshots.
cat >"$run/orca-map.json" <<'JSON'
{"schema": 1, "run_id": "run_sim", "complete": true, "gates": {"integration": "gate_7"},
 "tasks": {"be-users-api": "task_1", "be-users-tests": "task_2", "fe-users-screen": "task_3",
           "fe-users-tests": "task_4", "review-engine": "task_5", "review-frontend": "task_6",
           "integration": "task_7"}}
JSON
task_list() {
  # task_list <status of task_1..task_7>: an `orca orchestration task-list --json --full` response
  printf '{"ok": true, "result": {"tasks": [%s]}}\n' "$(
    i=0
    for st in "$@"; do
      i=$((i + 1))
      [ $i -gt 1 ] && printf ', '
      printf '{"id": "task_%s", "status": "%s"}' "$i" "$st"
    done
  )"
}

step "5. Status right after the Run is created: wave 1 ready, the rest waiting"
task_list ready ready ready ready pending pending pending >"$tmp/orca-1.json"
"$th" status --run-dir "$run" --orca-json "$tmp/orca-1.json"

eng="$tmp/repos/tte-engine"
fe="$tmp/repos/tte-frontend"

step "6. be-users-tests: a QA worker oversteps (edits the contract) and leaves the tree dirty"
git -C "$eng" checkout -q -b test/users-api-tests
echo "def test_list_users(): ..." >"$eng/src/test_users.py"
echo '{"openapi": "3.1.0", "paths": {"/api/v1/users": {}}}' >"$eng/openapi.json"
git -C "$eng" add -A && git -C "$eng" commit -q -m "test: users API scenarios"
echo "scratch" >"$eng/src/notes.txt"
"$th" evidence run --run-dir "$run" --task be-users-tests --repo-dir "$eng"
echo "--- evidence check (must fail: dirty tree, contract changed, no review yet)"
expect_fail "$th" evidence check --run-dir "$run" --task be-users-tests

step "7. The worker fixes it: contract restored, tree clean; development gates pass"
rm "$eng/src/notes.txt"
git -C "$eng" checkout -q main -- openapi.json
git -C "$eng" commit -q -m "test: keep the contract as approved"
"$th" evidence run --run-dir "$run" --task be-users-tests --repo-dir "$eng"
echo "--- evidence check (development gates pass; review still missing)"
expect_fail "$th" evidence check --run-dir "$run" --task be-users-tests

step "8. be-users-api: the approved contract change is allowed for this task only"
git -C "$eng" checkout -q main
git -C "$eng" checkout -q -b feat/users-api
echo "router: GET /api/v1/users" >"$eng/src/users.txt"
echo '{"openapi": "3.1.0", "paths": {"/api/v1/users": {"get": {}}}}' >"$eng/openapi.json"
git -C "$eng" add -A && git -C "$eng" commit -q -m "feat: list users"
"$th" evidence run --run-dir "$run" --task be-users-api --repo-dir "$eng"

step "9. An independent reviewer records verdicts from clean checkouts"
printf '# Review of be-users-api\n\nNo critical findings. Tenant scoping checked on every query.\n' >"$tmp/findings-api.md"
"$th" evidence review --run-dir "$run" --task be-users-api --repo-dir "$eng" \
  --verdict pass --critical 0 --attest security-reviewed --findings "$tmp/findings-api.md" --reviewer sim-reviewer
"$th" evidence check --run-dir "$run" --task be-users-api
git -C "$eng" checkout -q test/users-api-tests
printf '# Review of be-users-tests\n\nB-1..B-10 present and mapped to AC-1..AC-6.\n' >"$tmp/findings-tests.md"
"$th" evidence review --run-dir "$run" --task be-users-tests --repo-dir "$eng" \
  --verdict pass --critical 0 --attest tests-cover-criteria --findings "$tmp/findings-tests.md" --reviewer sim-reviewer
"$th" evidence check --run-dir "$run" --task be-users-tests
echo "--- a reviewer cannot record a verdict from a modified checkout"
echo "tweak" >>"$eng/src/test_users.py"
expect_fail "$th" evidence review --run-dir "$run" --task be-users-tests --repo-dir "$eng" \
  --verdict pass --critical 0 --reviewer sim-reviewer
git -C "$eng" checkout -q -- src/test_users.py

step "10. fe-users-screen: built against the contract through the mock engine, validated"
git -C "$fe" checkout -q -b feat/users-screen
echo "Users screen" >"$fe/src/users-screen.txt"
git -C "$fe" add -A && git -C "$fe" commit -q -m "feat: users screen"
"$th" evidence run --run-dir "$run" --task fe-users-screen --repo-dir "$fe"

step "11. Status later: engine side reviewed, frontend in review, one worker owes evidence"
#            be-api    be-tests  fe-screen fe-tests  rev-eng   rev-fe     integration
task_list completed completed completed completed completed dispatched blocked >"$tmp/orca-2.json"
"$th" status --run-dir "$run" --orca-json "$tmp/orca-2.json" | tee "$tmp/status.txt"
for want in "COMPLETED       be-users-api" "COMPLETED       be-users-tests" \
  "REVIEW          fe-users-screen" "VALIDATING      fe-users-tests" \
  "COMPLETED       review-engine" "RUNNING         review-frontend" \
  "NEEDS_APPROVAL  integration"; do
  grep -q "$want" "$tmp/status.txt" || { echo "UNEXPECTED: status lacks '$want'" >&2; exit 1; }
done

step "12. The integration task's gates: PR and CI not recorded, merge approval is a person's"
expect_fail "$th" evidence check --run-dir "$run" --task integration

step "Simulation passed: nothing outside $tmp was touched"
