from __future__ import annotations

import json
import os
import shutil
import string
import tempfile
import unittest
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from unittest import mock

from hypothesis import given, seed, settings, strategies as st

from state_contract import accepts_state, check_state_bytes
from test_hardware import HARDWARE, HardwareTestCase
from test_power_toggle import POWER_TOGGLE, ROOT


def property_check(**strategies):
    def decorate(test):
        return seed(int(os.environ.get("POWER_TOGGLE_TEST_SEED", "0")))(
            settings(
                max_examples=int(os.environ.get("POWER_TOGGLE_TEST_EXAMPLES", "100")),
                database=None, deadline=None,
            )(given(**strategies)(test))
        )
    return decorate


PATHS = st.one_of(
    st.just("/"),
    st.lists(
        st.text(string.ascii_letters + string.digits + "_", min_size=1, max_size=12),
        min_size=1, max_size=4,
    ).map(lambda parts: "/" + "/".join(parts)),
)
JSON_VALUES = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(
        allow_nan=False, allow_infinity=False,
    ) | st.text() | st.just("\ud800"),
    lambda values: st.lists(values, max_size=5) | st.dictionaries(
        st.text(), values, max_size=5,
    ),
    max_leaves=20,
)


@st.composite
def saved_states(draw):
    version = draw(st.sampled_from((1, 2, 3)))
    state = {
        "version": version,
        "extension_enabled": draw(st.booleans()),
        "clock_show_seconds": draw(st.booleans()),
    }
    if version >= 2:
        state["keyboard_backlights"] = draw(st.dictionaries(
            PATHS, st.integers(0, 2**31 - 1), max_size=4,
        ))
    if version == 3:
        state["keyboard_backlight_percentage"] = (
            draw(st.integers(0, 100)) if state["keyboard_backlights"] else None
        )
    return state


@st.composite
def candidate_states(draw):
    state = draw(saved_states())
    key = draw(st.sampled_from((
        "version", "extension_enabled", "clock_show_seconds",
        "keyboard_backlights", "keyboard_backlight_percentage",
    )))
    if draw(st.booleans()):
        state.pop(key, None)
    else:
        state[key] = draw(JSON_VALUES | st.dictionaries(
            PATHS | st.text(), JSON_VALUES, max_size=4,
        ))
    return state


@st.composite
def nul_path_states(draw):
    state = draw(saved_states())
    state["version"] = 2
    state["keyboard_backlights"] = {
        draw(PATHS) + "\0": draw(st.integers(0, 2**31 - 1)),
    }
    return state


STATE_INPUTS = saved_states() | candidate_states() | nul_path_states()


class StateProperties(unittest.TestCase):
    @property_check(value=JSON_VALUES | STATE_INPUTS)
    def test_schema_matches_independent_contract(self, value):
        try:
            actual = POWER_TOGGLE.validate_state(value)
        except ValueError:
            self.assertFalse(accepts_state(value))
        else:
            self.assertTrue(accepts_state(value))
            self.assertIs(actual, value)

    @property_check(state=saved_states())
    def test_saved_baseline_round_trip_is_private_and_lossless(self, state):
        with tempfile.TemporaryDirectory(prefix=".test-state-", dir=ROOT) as directory:
            state_dir = Path(directory) / "state"
            path = state_dir / "pre-battery-state.json"
            with (
                mock.patch.object(POWER_TOGGLE, "STATE_DIR", state_dir),
                mock.patch.object(POWER_TOGGLE, "STATE_FILE", path),
            ):
                POWER_TOGGLE.save_state(state)
                self.assertEqual(POWER_TOGGLE.load_saved_state(), state)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(state_dir.stat().st_mode & 0o777, 0o700)
            self.assertEqual(list(state_dir.iterdir()), [path])

    @property_check(data=st.binary(max_size=4096) | STATE_INPUTS.map(
        lambda state: json.dumps(state).encode("utf-8"),
    ))
    def test_state_bytes_follow_schema_without_changing_baseline(self, data):
        with tempfile.TemporaryDirectory(prefix=".test-state-", dir=ROOT) as directory:
            check_state_bytes(data, Path(directory) / "state.json")

    def test_fuzz_corpus(self):
        corpus = sorted((ROOT / "tests/corpus/state").iterdir())
        self.assertTrue(corpus, "the committed corpus must contain seeds")
        with tempfile.TemporaryDirectory(prefix=".test-state-", dir=ROOT) as directory:
            for path in corpus:
                with self.subTest(seed=path.name):
                    check_state_bytes(path.read_bytes(), Path(directory) / "state.json")


class KeyboardProperties(unittest.TestCase):
    @property_check(maximum=st.integers(1, 2**31 - 1), fraction=st.fractions(0, 1))
    def test_percentage_uses_half_up_rounding(self, maximum, fraction):
        level = int(maximum * fraction)
        path = "/keyboard"
        expected = int((Decimal(level) * 100 / Decimal(maximum)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP,
        ))
        with (
            mock.patch.object(POWER_TOGGLE, "keyboard_backlight_paths", return_value=[path]),
            mock.patch.object(POWER_TOGGLE, "keyboard_backlight_proxy"),
            mock.patch.object(POWER_TOGGLE, "read_keyboard_backlight_maximum", return_value=maximum),
        ):
            self.assertEqual(POWER_TOGGLE.keyboard_backlight_percentage({path: level}), expected)
            self.assertEqual(POWER_TOGGLE.keyboard_backlight_percentage({path: 0}), 0)
            self.assertEqual(POWER_TOGGLE.keyboard_backlight_percentage({path: maximum}), 100)


class HardwareProperties(HardwareTestCase):
    @property_check(
        battery=st.booleans(),
        cpu_maxima=st.lists(st.integers(1, 10**8), min_size=1, max_size=8),
        gpu_maxima=st.lists(st.integers(1, 10**5), min_size=1, max_size=4),
        cap=st.integers(1, 100), turbo=st.booleans(),
    )
    def test_policy_preserves_battery_caps_and_restores_ac_ceilings(
        self, battery, cpu_maxima, gpu_maxima, cap, turbo,
    ):
        # Each generated topology replaces the fixture; no stale engines survive.
        shutil.rmtree(self.cpu_root)
        shutil.rmtree(self.root / "class/drm")
        for index, maximum in enumerate(cpu_maxima):
            cpu = self.cpu_root / f"policy{index}"
            self.put(cpu / "cpuinfo_max_freq", str(maximum))
            self.put(cpu / "scaling_max_freq", str(max(1, maximum // 2)))
        for index, maximum in enumerate(gpu_maxima):
            gpu = self.gpu_root / f"gt{index}/freq0"
            self.put(gpu / "power_profile", "base [power_saving]")
            self.put(gpu / "rp0_freq", str(maximum))
            self.put(gpu / "max_freq", str(max(1, maximum // 2)))
            self.put(gpu / "min_freq", "1")
        self.put(self.pstate / "max_perf_pct", str(cap))
        self.put(self.pstate / "no_turbo", str(int(not turbo)))
        HARDWARE.configure_hardware(battery, self.root)
        for index, maximum in enumerate(cpu_maxima):
            cpu = self.cpu_root / f"policy{index}"
            self.assertEqual(int(HARDWARE.read(cpu / "scaling_max_freq")), max(1, maximum // 2) if battery else maximum)
            self.assertEqual(int(HARDWARE.read(cpu / "cpuinfo_max_freq")), maximum)
        for index, maximum in enumerate(gpu_maxima):
            gpu = self.gpu_root / f"gt{index}/freq0"
            self.assertEqual(int(HARDWARE.read(gpu / "max_freq")), max(1, maximum // 2) if battery else maximum)
            self.assertEqual(int(HARDWARE.read(gpu / "rp0_freq")), maximum)
            self.assertEqual(HARDWARE.read(gpu / "min_freq"), "1")
            self.assertEqual(HARDWARE.read(gpu / "power_profile"), "power_saving" if battery else "base")
        self.assertEqual(HARDWARE.read(self.pstate / "max_perf_pct"), str(cap) if battery else "100")
        self.assertEqual(HARDWARE.read(self.pstate / "no_turbo"), str(int(not turbo)) if battery else "0")
        self.assertEqual(HARDWARE.read(self.pstate / "hwp_dynamic_boost"), "0" if battery else "1")
