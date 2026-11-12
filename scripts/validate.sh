#!/usr/bin/env bash
# What CI runs: structural validation of the harness, then the test suite.
#   scripts/validate.sh            validate + tests
#   scripts/validate.sh --quick    validate only
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
"$root/bin/tte-harness" validate --warnings
if [ "${1:-}" = "--quick" ]; then
  exit 0
fi
cd "$root"
# The tests run under the same interpreter the CLI picks.
"$root/bin/tte-harness" --python -m unittest discover -s tests -t . "$@"
