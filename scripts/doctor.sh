#!/usr/bin/env bash
# Diagnose this host: tools, install state, Orca, repositories. Every FAIL prints a fix.
#   scripts/doctor.sh            human-readable
#   scripts/doctor.sh --json     machine-readable
#   scripts/doctor.sh --offline  skip the GitHub permission checks
set -euo pipefail
exec "$(cd "$(dirname "$0")/.." && pwd)/bin/tte-harness" doctor "$@"
