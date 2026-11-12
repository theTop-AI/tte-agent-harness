# External skill review

Fill this in for the exact commit under review and keep it with the approval (the PR that adds
the `external_skills` entry).

```markdown
Skill: <name>    Source: <URL>    Commit: <full sha>    Reviewer: <name>    Date: <YYYY-MM-DD>
```

## Provenance

- [ ] The source is the publisher's own repository, not a mirror or fork.
- [ ] The publisher maintains it (recent commits, issues answered) and states a licence that
      allows our use.
- [ ] The commit is pinned; a branch name or `latest` is not a version.

## Contents (read every file)

- [ ] `SKILL.md` instructions: nothing that tells an agent to ignore its rules, fetch and run
      remote content, exfiltrate data, or widen its own permissions.
- [ ] Scripts: each one read; no network calls, credential reads or writes outside the working
      directory without a stated reason.
- [ ] Hooks (`hooks:` in frontmatter, hook files): what runs, when, with which access.
- [ ] Tool permissions (`allowed-tools`, plugin manifests, MCP servers): least privilege.
- [ ] Binary or minified files: none, or each one justified and its origin verified.

## Fit

- [ ] It does not duplicate a harness skill; or it is clearly better and recorded as replacing it.
- [ ] Its name is not reserved and does not clash with an installed skill.
- [ ] It works for the providers we need (Claude Code, Codex) or says which one.

## Decision

approved / rejected / candidate (watch, not installed), with the reason.
