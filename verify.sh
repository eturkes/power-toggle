#!/usr/bin/bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd -- "$project_dir"
test_python=${UV_PROJECT_ENVIRONMENT:-.venv}/bin/python
export PYTHONHASHSEED=0 PYTHONOPTIMIZE=0
export POWER_TOGGLE_TEST_SEED=0 POWER_TOGGLE_TEST_EXAMPLES=100

"$test_python" -m unittest discover -s tests -q
/usr/bin/bash -n install.sh uninstall.sh install-hardware.sh uninstall-hardware.sh \
    verify.sh fuzz.sh
