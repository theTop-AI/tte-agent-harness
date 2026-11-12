#!/usr/bin/env bash
# Install the harness agents and skills for the current user (no root needed).
#
#   scripts/install.sh --dry-run                       show what would change, write nothing
#   scripts/install.sh                                 install for the providers found here
#   scripts/install.sh --ref v0.1.0                    refuse unless the checkout is at v0.1.0
#   scripts/install.sh --providers claude,codex        choose the targets
#   scripts/install.sh --with-orca-skills              also install Orca's orca-cli and orchestration skills
#   scripts/install.sh --with-permissions              also add the deny/ask rules to Claude settings.json
#
# Safe to run again: unchanged files are left alone, files you edited are reported as conflicts
# and kept (--force backs them up first). Full flag list: scripts/install.sh --help
set -euo pipefail
exec "$(cd "$(dirname "$0")/.." && pwd)/bin/tte-harness" install "$@"
