# Getting started

Install the harness for one user, check the host, keep it up to date, remove it. Everything here
runs as that user; only the optional system packages in step 1 need `sudo`.

The primary target is the AWS devbox `tte-devbox-vlad` (Ubuntu 24.04, user `ubuntu`, SSH through
AWS Systems Manager). The same commands work on macOS for local use.

> **Verification status.** The commands below were run on macOS (2026-11-12). The devbox was not
> reachable from the session that wrote this guide (expired AWS SSO token), so every step marked
> *unverified on the devbox* is the documented procedure, not an observed run. `scripts/doctor.sh`
> tells you on the host what holds and what does not.

## 0. Reach the devbox

From your laptop (the SSH config's `ProxyCommand` runs `aws ssm start-session` with profile
`tte-dev`):

```bash
aws sso login --profile tte-dev
ssh tte-devbox-vlad
```

An `Error when retrieving token from sso: Token has expired` from `ssh` means the first command is
needed again.

## 1. Prerequisites on the host

```bash
git --version                      # 2.17+ (Orca worktrees)
python3 --version                  # 3.10+ (Ubuntu 24.04: 3.12)
python3 -c 'import yaml; print(yaml.__version__)'   # PyYAML; preinstalled on Ubuntu EC2 images
gh --version && gh auth status
claude --version                   # Claude Code, required
codex --version                    # Codex CLI, optional
```

What to do when one is missing (*unverified on the devbox*):

| Missing | Install |
|---|---|
| PyYAML | `sudo apt-get install -y python3-yaml` |
| gh | `sudo apt-get install -y gh`, then `gh auth login` and `gh auth setup-git` |
| Claude Code | the official installer from https://code.claude.com/docs (read the script before running it) |
| Codex | `npm install -g @openai/codex`, then `codex login` (optional) |

The harness itself never asks for `sudo`, writes nothing outside your home folder, and never
installs these tools for you.

## 2. Clone the harness at a pinned revision

```bash
mkdir -p ~/projects
git clone https://github.com/theTop-AI/tte-agent-harness.git ~/projects/tte-agent-harness
cd ~/projects/tte-agent-harness
git checkout <tag-or-commit>        # e.g. v0.1.0 once it is tagged; a full commit SHA until then
```

Install from a tag or commit, never from a moving branch: the installer records exactly which
revision it installed, and `--ref` refuses to run when the checkout is somewhere else.

## 3. Tell the harness where the product repositories are

```bash
cp config/repositories.example.yaml config/repositories.yaml   # git-ignored, per host
$EDITOR config/repositories.yaml                               # set each `path:`
```

The example already uses `/home/ubuntu/projects/<repo>`. Clone any repository that is not there
yet (the harness never clones for you):

```bash
for r in tte-frontend tte-engine tte-infra tte-lab; do
  [ -d ~/projects/$r ] || git clone https://github.com/theTop-AI/$r.git ~/projects/$r
done
```

## 4. Validate, preview, install

```bash
bin/tte-harness validate                            # the harness source is consistent
scripts/install.sh --dry-run --ref <tag-or-commit>  # what would change; writes nothing
scripts/install.sh --ref <tag-or-commit>            # install
```

The installer detects Claude Code and Codex (binary or config folder) and installs for each one it
finds; `--providers claude` or `--providers claude,codex` chooses explicitly. It writes:

| What | Where |
|---|---|
| Claude Code skills | `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/<name>/` |
| Claude Code subagents | `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/<name>.md` |
| Codex skills | `~/.agents/skills/<name>/` |
| Codex custom agents | `${CODEX_HOME:-~/.codex}/agents/<name>.toml` |
| CLI | `~/.local/bin/tte-harness` (runs this checkout's `bin/tte-harness`) |
| Manifest | `~/.local/state/tte-agent-harness/install-manifest.json` |

If `~/.local/bin` is not on your `PATH` yet:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && . ~/.bashrc
tte-harness --version
```

Start a new Claude Code or Codex session afterwards: both read skills and agents at session start.

## 5. Orca's own skills (inside an Orca terminal on the host)

The official `orca-cli` and `orchestration` skills come from the Orca build itself. Install them
from a terminal that Orca opened on the devbox (Orca → the devbox workspace → new terminal):

```bash
cd ~/projects/tte-agent-harness
scripts/install.sh --dry-run --with-orca-skills     # also prints Orca's own dry run
scripts/install.sh --with-orca-skills
```

This runs `orca skills install --skill orca-cli --skill orchestration` through the CLI the official
skills resolve. Run it inside an Orca terminal because on Linux a bare `orca` outside Orca is
usually `/usr/bin/orca`, the GNOME screen reader; the harness refuses that binary and says so.
*Unverified on the devbox:* how the Orca CLI is exposed in that terminal. The harness accepts
`$ORCA_CLI_COMMAND`, then `orca-ide`, then an `orca` that is not `/usr/bin/orca` while
`ORCA_TERMINAL_HANDLE` or `ORCA_WORKTREE_ID` is set; `scripts/doctor.sh` prints which one it found. Connecting Orca to the devbox and turning on
orchestration: [orchestration.md](orchestration.md).

## 6. Optional: Claude Code permission rules

```bash
scripts/install.sh --dry-run --with-permissions     # lists each rule it would add
scripts/install.sh --with-permissions
```

It adds the `deny` and `ask` rules of `adapters/claude-code/permissions.json` to
`~/.claude/settings.json`: no reads of AWS, SSH or GitHub credentials, no merge, force-push, push to
`main`, `terraform apply`, `orca orchestration reset`; a person confirms `aws`, tags, releases and
edits to the harness's own configuration. Only missing rules are added, your other settings are
kept, the previous file is backed up, and uninstall removes exactly the rules it added. Read
[security.md](security.md) before turning it on.

## 7. Check the host

```bash
scripts/doctor.sh            # every FAIL and WARN prints its fix
scripts/doctor.sh --offline  # without the GitHub permission checks
scripts/doctor.sh --json     # for scripts
```

It checks Python, git and worktrees, gh and its login, Claude Code, Codex, the install manifest
against the files on disk, that every harness skill is installed, the Orca CLI, its bundled
orchestration guide, Orca's own skills, the Orca runtime and orchestration, each product
repository (checkout, worktrees, committed validation sequence) and your GitHub permission on it.
Orca checks only pass inside an Orca terminal with the runtime reachable.

If Orca launches Claude Code under a managed account, it sets its own `CLAUDE_CONFIG_DIR` for that
pane; doctor warns about it (`ORCA_CLAUDE_INJECTED_CONFIG_DIR`). Run the install from such a pane
too, or use the "System default" account, so that account sees the harness.

## 8. Update

```bash
cd ~/projects/tte-agent-harness
git fetch --tags
git checkout <new-tag>
scripts/install.sh --dry-run --ref <new-tag>
scripts/install.sh --ref <new-tag>
```

Unchanged files are left alone; files the harness owns are updated; files it no longer ships are
removed. A file you edited after the install is a **conflict**: it is kept, listed, and the
installer exits 3. Either restore it (`scripts/uninstall.sh` keeps edited files, so delete it by
hand) or replace it deliberately:

```bash
scripts/install.sh --ref <new-tag> --force   # backs every conflict up first
ls ~/.local/state/tte-agent-harness/backups/  # one folder per forced run
```

A skill folder holding a `SKILL.md` the harness did not install (your own skill of the same name)
is never mixed with harness files; `--force` moves it to the backup folder first.

## 9. Uninstall

```bash
scripts/uninstall.sh --dry-run
scripts/uninstall.sh
```

Removes every file the manifest lists that is still exactly as installed, the permission rules it
added, and the manifest. Edited files are reported and kept. Orca's own skills are Orca's: remove
them through Orca if you want them gone.

## Local use on macOS

The same commands, from any folder:

```bash
git clone https://github.com/theTop-AI/tte-agent-harness.git ~/work/tte-agent-harness
cd ~/work/tte-agent-harness
brew install uv                    # only when python3 has no PyYAML: the launcher then uses uv
scripts/install.sh --dry-run
scripts/install.sh
scripts/doctor.sh --offline
```

`bin/tte-harness` uses `python3` when it has PyYAML, else `uv run` with a pinned Python and PyYAML.
In that case uv keeps its own interpreter and package cache in `~/.local/share/uv` and
`~/.cache/uv` (measured: about 2,000 files on first use). That is uv's, not the harness's: a dry
run of the harness itself writes nothing, and uninstall leaves nothing behind but uv's cache.
On macOS a bare `orca` is Orca IDE's CLI (`/usr/local/bin/orca`), so `--with-orca-skills` works
from any terminal there.

## Try the example

```bash
examples/users-management/simulate.sh
```

The full lifecycle of a two-repository feature against throwaway repositories, with no Orca, GitHub
or network access: [examples/users-management](../examples/users-management/README.md).
