from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader(
    "power_toggle_under_test", str(ROOT / "power-toggle")
)
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
POWER_TOGGLE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(POWER_TOGGLE)


class PolicyStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix=".test-state-", dir=ROOT
        )
        self.addCleanup(self.temporary_directory.cleanup)
        state_directory = Path(self.temporary_directory.name) / "state"
        self.state_file = state_directory / "pre-battery-state.json"
        self.path_patches = (
            mock.patch.object(POWER_TOGGLE, "STATE_DIR", state_directory),
            mock.patch.object(POWER_TOGGLE, "STATE_FILE", self.state_file),
        )
        for patch in self.path_patches:
            patch.start()
            self.addCleanup(patch.stop)

        self.desktop = {"extension": True, "seconds": True}
        self.behavior_patches = (
            mock.patch.object(
                POWER_TOGGLE,
                "extension_is_enabled",
                side_effect=lambda: self.desktop["extension"],
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "seconds_are_enabled",
                side_effect=lambda: self.desktop["seconds"],
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "set_extension_enabled",
                side_effect=self.set_extension,
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "set_seconds_enabled",
                side_effect=self.set_seconds,
            ),
        )
        for patch in self.behavior_patches:
            patch.start()
            self.addCleanup(patch.stop)

    def set_extension(self, enabled: bool) -> bool:
        self.desktop["extension"] = enabled
        return True

    def set_seconds(self, enabled: bool) -> bool:
        self.desktop["seconds"] = enabled
        return True

    def test_battery_restart_preserves_baseline_then_restores(self) -> None:
        self.assertTrue(POWER_TOGGLE.apply_battery_policy())
        self.assertEqual(self.desktop, {"extension": False, "seconds": False})
        baseline = POWER_TOGGLE.load_saved_state()
        self.assertEqual(
            baseline,
            {
                "version": 1,
                "extension_enabled": True,
                "clock_show_seconds": True,
            },
        )

        self.assertTrue(POWER_TOGGLE.apply_battery_policy())
        self.assertEqual(POWER_TOGGLE.load_saved_state(), baseline)

        self.assertTrue(POWER_TOGGLE.restore_pre_battery_state())
        self.assertEqual(self.desktop, {"extension": True, "seconds": True})
        self.assertFalse(self.state_file.exists())

    def test_restore_preserves_originally_disabled_preferences(self) -> None:
        self.desktop = {"extension": False, "seconds": False}
        self.assertTrue(POWER_TOGGLE.apply_battery_policy())

        self.desktop = {"extension": True, "seconds": True}
        self.assertTrue(POWER_TOGGLE.restore_pre_battery_state())

        self.assertEqual(self.desktop, {"extension": False, "seconds": False})

    def test_invalid_state_blocks_mutation(self) -> None:
        self.state_file.parent.mkdir(parents=True)
        self.state_file.write_text('{"version": 99}\n', encoding="utf-8")

        with self.assertLogs("power-toggle", level="ERROR"):
            self.assertFalse(POWER_TOGGLE.apply_battery_policy())

        self.assertEqual(self.desktop, {"extension": True, "seconds": True})

    def test_failed_restore_retains_state_for_retry(self) -> None:
        POWER_TOGGLE.save_state(
            {
                "version": 1,
                "extension_enabled": True,
                "clock_show_seconds": True,
            }
        )
        POWER_TOGGLE.set_extension_enabled.side_effect = lambda _enabled: False

        with self.assertLogs("power-toggle", level="ERROR"):
            self.assertFalse(POWER_TOGGLE.restore_pre_battery_state())

        self.assertTrue(self.state_file.exists())

    def test_state_file_is_private_json(self) -> None:
        state = {
            "version": 1,
            "extension_enabled": True,
            "clock_show_seconds": False,
        }
        POWER_TOGGLE.save_state(state)

        self.assertEqual(json.loads(self.state_file.read_text(encoding="utf-8")), state)
        self.assertEqual(self.state_file.stat().st_mode & 0o777, 0o600)


class ExtensionMutationTests(unittest.TestCase):
    def test_unchanged_state_avoids_subprocess(self) -> None:
        with (
            mock.patch.object(POWER_TOGGLE, "extension_is_enabled", return_value=True),
            mock.patch.object(POWER_TOGGLE.subprocess, "run") as run,
        ):
            self.assertTrue(POWER_TOGGLE.set_extension_enabled(True))

        run.assert_not_called()

    def test_failed_enable_is_retryable_failure(self) -> None:
        result = mock.Mock(returncode=1, stderr="Extension not found", stdout="")
        with (
            mock.patch.object(POWER_TOGGLE, "extension_is_enabled", return_value=False),
            mock.patch.object(POWER_TOGGLE.subprocess, "run", return_value=result),
            self.assertLogs("power-toggle", level="ERROR"),
        ):
            self.assertFalse(POWER_TOGGLE.set_extension_enabled(True))


if __name__ == "__main__":
    unittest.main()
