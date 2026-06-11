#!/usr/bin/env bash
#
# DNA Guardian - Periodic Runner (eerste slice van Increment 6)
#
# Usage:
#   ./scripts/dna_guardian/run_periodic.sh
#   ./scripts/dna_guardian/run_periodic.sh --llm-review
#
# This script runs the DNA Guardian with --create-entry and optionally --llm-review.
# It is intended to be called from cron / task scheduler.
#
# Example cron (every day at 09:00):
#   0 9 * * * cd /path/to/ninjatraderai_bot && ./scripts/dna_guardian/run_periodic.sh >> logs/dna_guardian.log 2>&1
#

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GUARDIAN="$PROJECT_ROOT/scripts/dna_guardian/validate_dna.py"

echo "=== DNA Guardian periodic run started at $(date -Iseconds) ==="

cd "$PROJECT_ROOT"

if [[ "${1:-}" == "--llm-review" ]]; then
    python "$GUARDIAN" --create-entry --llm-review
else
    python "$GUARDIAN" --create-entry
fi

echo "=== DNA Guardian periodic run finished at $(date -Iseconds) ==="