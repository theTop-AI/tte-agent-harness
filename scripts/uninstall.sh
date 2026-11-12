#!/usr/bin/env bash
# Remove what scripts/install.sh wrote. Files edited after install are kept and reported.
#   scripts/uninstall.sh --dry-run    show what would be removed
set -euo pipefail
exec "$(cd "$(dirname "$0")/.." && pwd)/bin/tte-harness" uninstall "$@"
