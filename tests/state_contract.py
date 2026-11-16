"""Saved-state schema oracle; no GLib validation or desktop mutations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import mock

from test_power_toggle import POWER_TOGGLE


OBJECT_PATH = re.compile(r"/(?:[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*)?")


def valid_backlights(value):
    return isinstance(value, dict) and all(
        isinstance(path, str)
        and OBJECT_PATH.fullmatch(path) is not None
        and type(level) is int and 0 <= level < 2**31
        for path, level in value.items()
    )


def accepts_state(value):
    if not isinstance(value, dict):
        return False
    version = value.get("version")
    # JSON numeric versions retain compatibility with legacy integer-valued floats.
    if type(version) not in (int, float) or version not in (1, 2, 3):
        return False
    fields = {
        "extension_enabled": lambda v: type(v) is bool,
        "clock_show_seconds": lambda v: type(v) is bool,
    }
    if version >= 2:
        fields["keyboard_backlights"] = valid_backlights
    if version == 3:
        fields["keyboard_backlight_percentage"] = (
            (lambda v: type(v) is int and 0 <= v <= 100)
            if value.get("keyboard_backlights") else (lambda v: v is None)
        )
    return all(predicate(value.get(field)) for field, predicate in fields.items())


def check_state_bytes(data: bytes, path: Path):
    try:
        expected = json.loads(data.decode("utf-8"))
        accepted = accepts_state(expected)
    except (ValueError, RecursionError):
        accepted = False
    path.write_bytes(data)
    with mock.patch.object(POWER_TOGGLE, "STATE_FILE", path):
        try:
            actual = POWER_TOGGLE.load_saved_state()
        except ValueError:
            assert not accepted, "valid state rejected"
        else:
            assert accepted, "invalid state accepted"
            assert actual == expected, "loaded state changed"
    assert path.read_bytes() == data, "loading changed the saved baseline"
