"""Coverage-guided JSON-state campaign; corpus replay lives in test_properties."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import atheris

from state_contract import accepts_state, check_state_bytes, valid_backlights
from test_power_toggle import POWER_TOGGLE


def main():
    for function in (
        POWER_TOGGLE.validate_state, POWER_TOGGLE.load_saved_state,
        accepts_state, valid_backlights, check_state_bytes,
    ):
        atheris.instrument_func(function)
    # Atheris exits without Python finalizers; the parent shell owns all scratch files.
    path = Path(os.environ["POWER_TOGGLE_FUZZ_STATE_DIR"]) / "state.json"

    @atheris.instrument_func
    def test_one_input(data):
        check_state_bytes(data, path)

    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
