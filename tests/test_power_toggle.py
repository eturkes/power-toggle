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
        self.keyboard_path = (
            "/org/freedesktop/UPower/KbdBacklight/tpacpiookbd_backlight"
        )
        self.keyboard_backlights = {self.keyboard_path: 2}
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
            mock.patch.object(
                POWER_TOGGLE,
                "keyboard_backlight_brightnesses",
                side_effect=lambda: dict(self.keyboard_backlights),
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "set_keyboard_backlights",
                side_effect=self.set_keyboard_backlights,
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

    def set_keyboard_backlights(self, brightnesses: dict[str, int]) -> bool:
        self.keyboard_backlights.update(brightnesses)
        return True

    def test_battery_restart_preserves_baseline_then_restores(self) -> None:
        self.assertTrue(POWER_TOGGLE.apply_battery_policy())
        self.assertEqual(self.desktop, {"extension": False, "seconds": False})
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 0})
        baseline = POWER_TOGGLE.load_saved_state()
        self.assertEqual(
            baseline,
            {
                "version": 2,
                "extension_enabled": True,
                "clock_show_seconds": True,
                "keyboard_backlights": {self.keyboard_path: 2},
            },
        )

        self.assertTrue(POWER_TOGGLE.apply_battery_policy())
        self.assertEqual(POWER_TOGGLE.load_saved_state(), baseline)

        self.assertTrue(POWER_TOGGLE.restore_pre_battery_state())
        self.assertEqual(self.desktop, {"extension": True, "seconds": True})
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 2})
        self.assertFalse(self.state_file.exists())

    def test_restore_preserves_originally_disabled_preferences(self) -> None:
        self.desktop = {"extension": False, "seconds": False}
        self.keyboard_backlights[self.keyboard_path] = 0
        self.assertTrue(POWER_TOGGLE.apply_battery_policy())

        self.desktop = {"extension": True, "seconds": True}
        self.keyboard_backlights[self.keyboard_path] = 2
        self.assertTrue(POWER_TOGGLE.restore_pre_battery_state())

        self.assertEqual(self.desktop, {"extension": False, "seconds": False})
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 0})

    def test_invalid_state_blocks_mutation(self) -> None:
        self.state_file.parent.mkdir(parents=True)
        self.state_file.write_text('{"version": 99}\n', encoding="utf-8")

        with self.assertLogs("power-toggle", level="ERROR"):
            self.assertFalse(POWER_TOGGLE.apply_battery_policy())

        self.assertEqual(self.desktop, {"extension": True, "seconds": True})
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 2})

    def test_failed_restore_retains_state_for_retry(self) -> None:
        POWER_TOGGLE.save_state(
            {
                "version": 2,
                "extension_enabled": True,
                "clock_show_seconds": True,
                "keyboard_backlights": {self.keyboard_path: 2},
            }
        )
        POWER_TOGGLE.set_extension_enabled.side_effect = lambda _enabled: False

        with self.assertLogs("power-toggle", level="ERROR"):
            self.assertFalse(POWER_TOGGLE.restore_pre_battery_state())

        self.assertTrue(self.state_file.exists())

    def test_state_file_is_private_json(self) -> None:
        state = {
            "version": 2,
            "extension_enabled": True,
            "clock_show_seconds": False,
            "keyboard_backlights": {self.keyboard_path: 2},
        }
        POWER_TOGGLE.save_state(state)

        self.assertEqual(json.loads(self.state_file.read_text(encoding="utf-8")), state)
        self.assertEqual(self.state_file.stat().st_mode & 0o777, 0o600)

    def test_legacy_state_adds_keyboard_baseline_on_battery(self) -> None:
        POWER_TOGGLE.save_state(
            {
                "version": 1,
                "extension_enabled": True,
                "clock_show_seconds": True,
            }
        )

        self.assertTrue(POWER_TOGGLE.apply_battery_policy())
        self.assertEqual(
            POWER_TOGGLE.load_saved_state(),
            {
                "version": 2,
                "extension_enabled": True,
                "clock_show_seconds": True,
                "keyboard_backlights": {self.keyboard_path: 2},
            },
        )
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 0})

        self.assertTrue(POWER_TOGGLE.restore_pre_battery_state())
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 2})

    def test_legacy_state_restores_without_mutating_keyboard(self) -> None:
        POWER_TOGGLE.save_state(
            {
                "version": 1,
                "extension_enabled": True,
                "clock_show_seconds": True,
            }
        )

        self.assertTrue(POWER_TOGGLE.restore_pre_battery_state())

        POWER_TOGGLE.set_keyboard_backlights.assert_not_called()

    def test_keyboard_snapshot_failure_blocks_all_mutation(self) -> None:
        POWER_TOGGLE.keyboard_backlight_brightnesses.side_effect = RuntimeError(
            "keyboard backlight unavailable"
        )

        with self.assertLogs("power-toggle", level="ERROR"):
            self.assertFalse(POWER_TOGGLE.apply_battery_policy())

        POWER_TOGGLE.set_extension_enabled.assert_not_called()
        POWER_TOGGLE.set_seconds_enabled.assert_not_called()
        POWER_TOGGLE.set_keyboard_backlights.assert_not_called()
        self.assertFalse(self.state_file.exists())

    def test_failed_keyboard_restore_retains_state_for_retry(self) -> None:
        POWER_TOGGLE.save_state(
            {
                "version": 2,
                "extension_enabled": True,
                "clock_show_seconds": True,
                "keyboard_backlights": {self.keyboard_path: 2},
            }
        )
        POWER_TOGGLE.set_keyboard_backlights.side_effect = lambda _state: False

        with self.assertLogs("power-toggle", level="ERROR"):
            self.assertFalse(POWER_TOGGLE.restore_pre_battery_state())

        self.assertTrue(self.state_file.exists())

    def test_invalid_keyboard_brightness_is_rejected(self) -> None:
        for brightness in (-1, 2**31, True):
            with (
                self.subTest(brightness=brightness),
                self.assertRaisesRegex(ValueError, "keyboard backlight"),
            ):
                POWER_TOGGLE.validate_state(
                    {
                        "version": 2,
                        "extension_enabled": True,
                        "clock_show_seconds": True,
                        "keyboard_backlights": {
                            self.keyboard_path: brightness
                        },
                    }
                )


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


class KeyboardBacklightMutationTests(unittest.TestCase):
    PATH = "/org/freedesktop/UPower/KbdBacklight/tpacpiookbd_backlight"

    def test_enumerates_and_reads_keyboard_backlights(self) -> None:
        root_proxy = mock.Mock()
        root_proxy.call_sync.return_value = POWER_TOGGLE.GLib.Variant(
            "(ao)", ([self.PATH],)
        )
        backlight_proxy = mock.Mock()
        backlight_proxy.call_sync.return_value = POWER_TOGGLE.GLib.Variant(
            "(i)", (2,)
        )

        with (
            mock.patch.object(
                POWER_TOGGLE, "upower_proxy", return_value=root_proxy
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "keyboard_backlight_proxy",
                return_value=backlight_proxy,
            ),
        ):
            brightnesses = POWER_TOGGLE.keyboard_backlight_brightnesses()

        self.assertEqual(brightnesses, {self.PATH: 2})

    def test_unchanged_brightness_avoids_set_call(self) -> None:
        proxy = mock.Mock()
        proxy.call_sync.return_value = POWER_TOGGLE.GLib.Variant("(i)", (2,))

        with mock.patch.object(
            POWER_TOGGLE, "keyboard_backlight_proxy", return_value=proxy
        ):
            self.assertTrue(POWER_TOGGLE.set_keyboard_backlight(self.PATH, 2))

        self.assertEqual(
            [call.args[0] for call in proxy.call_sync.call_args_list],
            ["GetBrightness"],
        )

    def test_changed_brightness_is_set_and_verified(self) -> None:
        proxy = mock.Mock()
        proxy.call_sync.side_effect = (
            POWER_TOGGLE.GLib.Variant("(i)", (2,)),
            POWER_TOGGLE.GLib.Variant("()", ()),
            POWER_TOGGLE.GLib.Variant("(i)", (0,)),
        )

        with mock.patch.object(
            POWER_TOGGLE, "keyboard_backlight_proxy", return_value=proxy
        ):
            self.assertTrue(POWER_TOGGLE.set_keyboard_backlight(self.PATH, 0))

        self.assertEqual(
            [call.args[0] for call in proxy.call_sync.call_args_list],
            ["GetBrightness", "SetBrightness", "GetBrightness"],
        )
        self.assertEqual(proxy.call_sync.call_args_list[1].args[1].unpack(), (0,))

    def test_failed_verification_is_retryable_failure(self) -> None:
        proxy = mock.Mock()
        proxy.call_sync.side_effect = (
            POWER_TOGGLE.GLib.Variant("(i)", (2,)),
            POWER_TOGGLE.GLib.Variant("()", ()),
            POWER_TOGGLE.GLib.Variant("(i)", (2,)),
        )

        with (
            mock.patch.object(
                POWER_TOGGLE, "keyboard_backlight_proxy", return_value=proxy
            ),
            self.assertLogs("power-toggle", level="ERROR"),
        ):
            self.assertFalse(POWER_TOGGLE.set_keyboard_backlight(self.PATH, 0))


if __name__ == "__main__":
    unittest.main()
