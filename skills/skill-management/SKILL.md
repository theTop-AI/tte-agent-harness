---
name: skill-management
description: >-
  Use when adding, changing, reviewing or installing a skill: author a harness skill, version it,
  validate and install it, or vet an external third-party skill (review every file, pin an exact
  commit, record approval) before anything is installed. Never install unreviewed skills.
metadata:
  category: delivery
  version: "1.0.0"
---

# Skill management

Skills are instructions every agent on the host will follow, so a skill is code: reviewed,
pinned, versioned and installed only through the harness.

## When to use

- Writing or changing a skill in the harness repository.
- Someone proposes a third-party skill (a marketplace, `npx skills`, a plugin, a GitHub repo).
- `tte-harness doctor` reports a skill missing, edited after install, or in conflict.

## Inputs

- The harness checkout: `skills/`, `config/harness.yaml` (`reserved`, `external_skills`).
- For an external skill: its source URL and the exact commit or release under consideration.

## Procedure

Harness skills:

1. One folder `skills/<name>/` with `SKILL.md`: frontmatter `name` (equals the folder,
   lowercase-hyphenated, at most 64 characters), `description` (what it does and "Use when ...",
   trigger words first, short: Codex truncates the skills list), and `metadata` with `category`
   and `version` as strings. Body sections: When to use, Inputs, Procedure, Outputs, Validation,
   Escalate when. Under 500 lines; detail goes to `references/`, linked from `SKILL.md`.
2. The name must not be in `reserved.skills` (names Claude Code bundles, or that tte-workflows or
   Orca install into the same folders); a clash shadows one of the two.
3. Bump `metadata.version` (semver): patch for wording, minor for a new step, major when an
   agent relying on it must change.
4. `tte-harness validate`; add the skill to the agents that use it; commit through a PR.
5. Install from a commit: `scripts/install.sh --dry-run`, then `scripts/install.sh` (optionally
   `--ref <tag>`). Files edited after install show as conflicts and are kept; `--force` backs
   them up first. Start a new session to pick up changes.

External skills:

1. Never run `npx skills add`, `claude plugin install`, `orca plugin install` or copy a skill
   folder without a person's approval for that exact source and commit.
2. Review with [the external skill checklist](references/external-review.md): read every file,
   every script, every network call, hook and tool permission it asks for.
3. If it is approved, record it in `config/harness.yaml` `external_skills`: name, source URL,
   exact commit, reviewer, date, status `approved`. Vendor it into `skills/` only if it fits the
   harness format; otherwise install it with its own tool, pinned to that commit.
4. If an established, maintained skill does the job better than a harness one, record it as a
   `candidate` there instead of rewriting it.

## Outputs

- A validated skill folder and version bump, or an `external_skills` entry with its review.
- An install report from `scripts/install.sh` (created, updated, conflicts).

## Validation

- `tte-harness validate` has no error for the skill; `tte-harness doctor` shows it installed.
- An external skill's recorded commit is the one that was reviewed.

## Escalate when

- An external skill runs scripts, opens network connections, registers hooks or asks for broad
  tool permissions: a person decides, with the review in hand.
- A wanted name is reserved, or a skill would override another tool's behaviour.
