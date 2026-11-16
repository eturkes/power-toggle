#!/usr/bin/bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd -- "$project_dir"
test_python=${UV_PROJECT_ENVIRONMENT:-.venv}/bin/python
campaign=$(mktemp -d "$project_dir/.verify.campaign.XXXXXX")
mkdir -- "$campaign/corpus" "$campaign/state"
cp -- tests/corpus/state/* "$campaign/corpus/"
export PYTHONHASHSEED=0 PYTHONOPTIMIZE=0
export POWER_TOGGLE_FUZZ_STATE_DIR="$campaign/state"

if "$test_python" tests/fuzz_state.py "$campaign/corpus" -seed=1 \
    -max_total_time="${1:-30}" -max_len=65536 -artifact_prefix="$campaign/"; then
    rm -r -- "$campaign"
else
    rc=$?
    printf 'Inspect the failed campaign: %s\n' "$campaign" >&2
    exit "$rc"
fi
