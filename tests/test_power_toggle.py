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


class DesktopTestCase(unittest.TestCase):
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
        self.gnome_keyboard_percentage = 100
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
                "keyboard_backlight_percentage",
                side_effect=lambda brightnesses: (
                    brightnesses[self.keyboard_path] * 50
                    if brightnesses
                    else None
                ),
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

    def set_keyboard_backlights(
        self, brightnesses: dict[str, int], percentage: int | None
    ) -> bool:
        self.keyboard_backlights.update(brightnesses)
        self.gnome_keyboard_percentage = percentage
        return True


class PolicyStateTests(DesktopTestCase):
    def test_battery_restart_preserves_baseline_then_restores(self) -> None:
        self.assertTrue(POWER_TOGGLE.apply_battery_policy())
        self.assertEqual(self.desktop, {"extension": False, "seconds": False})
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 0})
        self.assertEqual(self.gnome_keyboard_percentage, 0)
        baseline = POWER_TOGGLE.load_saved_state()
        self.assertEqual(
            baseline,
            {
                "version": 3,
                "extension_enabled": True,
                "clock_show_seconds": True,
                "keyboard_backlights": {self.keyboard_path: 2},
                "keyboard_backlight_percentage": 100,
            },
        )

        self.assertTrue(POWER_TOGGLE.apply_battery_policy())
        self.assertEqual(POWER_TOGGLE.load_saved_state(), baseline)

        self.assertTrue(POWER_TOGGLE.restore_pre_battery_state())
        self.assertEqual(self.desktop, {"extension": True, "seconds": True})
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 2})
        self.assertEqual(self.gnome_keyboard_percentage, 100)
        self.assertFalse(self.state_file.exists())

    def test_restore_preserves_originally_disabled_preferences(self) -> None:
        self.desktop = {"extension": False, "seconds": False}
        self.keyboard_backlights[self.keyboard_path] = 0
        self.gnome_keyboard_percentage = 0
        self.assertTrue(POWER_TOGGLE.apply_battery_policy())

        self.desktop = {"extension": True, "seconds": True}
        self.keyboard_backlights[self.keyboard_path] = 2
        self.gnome_keyboard_percentage = 100
        self.assertTrue(POWER_TOGGLE.restore_pre_battery_state())

        self.assertEqual(self.desktop, {"extension": False, "seconds": False})
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 0})
        self.assertEqual(self.gnome_keyboard_percentage, 0)

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
                "version": 3,
                "extension_enabled": True,
                "clock_show_seconds": True,
                "keyboard_backlights": {self.keyboard_path: 2},
                "keyboard_backlight_percentage": 100,
            }
        )
        POWER_TOGGLE.set_extension_enabled.side_effect = lambda _enabled: False

        with self.assertLogs("power-toggle", level="ERROR"):
            self.assertFalse(POWER_TOGGLE.restore_pre_battery_state())

        self.assertTrue(self.state_file.exists())

    def test_state_file_is_private_json(self) -> None:
        state = {
            "version": 3,
            "extension_enabled": True,
            "clock_show_seconds": False,
            "keyboard_backlights": {self.keyboard_path: 2},
            "keyboard_backlight_percentage": 100,
        }
        POWER_TOGGLE.save_state(state)

        self.assertEqual(json.loads(self.state_file.read_text(encoding="utf-8")), state)
        self.assertEqual(self.state_file.stat().st_mode & 0o777, 0o600)

    def test_v1_state_adds_keyboard_baseline_on_battery(self) -> None:
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
                "version": 3,
                "extension_enabled": True,
                "clock_show_seconds": True,
                "keyboard_backlights": {self.keyboard_path: 2},
                "keyboard_backlight_percentage": 100,
            },
        )
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 0})
        self.assertEqual(self.gnome_keyboard_percentage, 0)

        self.assertTrue(POWER_TOGGLE.restore_pre_battery_state())
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 2})
        self.assertEqual(self.gnome_keyboard_percentage, 100)

    def test_v2_state_adds_gnome_menu_baseline_on_battery(self) -> None:
        POWER_TOGGLE.save_state(
            {
                "version": 2,
                "extension_enabled": True,
                "clock_show_seconds": True,
                "keyboard_backlights": {self.keyboard_path: 2},
            }
        )
        self.keyboard_backlights[self.keyboard_path] = 0
        self.gnome_keyboard_percentage = 0

        self.assertTrue(POWER_TOGGLE.apply_battery_policy())
        self.assertEqual(
            POWER_TOGGLE.load_saved_state(),
            {
                "version": 3,
                "extension_enabled": True,
                "clock_show_seconds": True,
                "keyboard_backlights": {self.keyboard_path: 2},
                "keyboard_backlight_percentage": 100,
            },
        )
        self.assertEqual(self.gnome_keyboard_percentage, 0)

        self.assertTrue(POWER_TOGGLE.restore_pre_battery_state())
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 2})
        self.assertEqual(self.gnome_keyboard_percentage, 100)

    def test_v2_state_restores_gnome_menu_on_external_power(self) -> None:
        POWER_TOGGLE.save_state(
            {
                "version": 2,
                "extension_enabled": True,
                "clock_show_seconds": True,
                "keyboard_backlights": {self.keyboard_path: 2},
            }
        )
        self.keyboard_backlights[self.keyboard_path] = 0
        self.gnome_keyboard_percentage = 0

        self.assertTrue(POWER_TOGGLE.restore_pre_battery_state())

        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 2})
        self.assertEqual(self.gnome_keyboard_percentage, 100)
        self.assertFalse(self.state_file.exists())

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

    def test_keyboard_percentage_failure_blocks_all_mutation(self) -> None:
        POWER_TOGGLE.keyboard_backlight_percentage.side_effect = RuntimeError(
            "keyboard backlight maximum unavailable"
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
                "version": 3,
                "extension_enabled": True,
                "clock_show_seconds": True,
                "keyboard_backlights": {self.keyboard_path: 2},
                "keyboard_backlight_percentage": 100,
            }
        )
        POWER_TOGGLE.set_keyboard_backlights.side_effect = (
            lambda _state, _percentage: False
        )

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
                        "version": 3,
                        "extension_enabled": True,
                        "clock_show_seconds": True,
                        "keyboard_backlights": {
                            self.keyboard_path: brightness
                        },
                        "keyboard_backlight_percentage": 100,
                    }
                )

    def test_invalid_keyboard_percentage_is_rejected(self) -> None:
        for percentage in (-1, 101, True, None):
            with (
                self.subTest(percentage=percentage),
                self.assertRaisesRegex(ValueError, "keyboard backlight percentage"),
            ):
                POWER_TOGGLE.validate_state(
                    {
                        "version": 3,
                        "extension_enabled": True,
                        "clock_show_seconds": True,
                        "keyboard_backlights": {self.keyboard_path: 2},
                        "keyboard_backlight_percentage": percentage,
                    }
                )

    def test_empty_keyboard_state_requires_no_gnome_percentage(self) -> None:
        state = {
            "version": 3,
            "extension_enabled": True,
            "clock_show_seconds": True,
            "keyboard_backlights": {},
            "keyboard_backlight_percentage": None,
        }

        self.assertIs(POWER_TOGGLE.validate_state(state), state)


class ExtensionMutationTests(unittest.TestCase):
    def test_unchanged_state_avoids_mutation(self) -> None:
        proxy = mock.Mock()
        with (
            mock.patch.object(POWER_TOGGLE, "extension_is_enabled", return_value=True),
            mock.patch.object(
                POWER_TOGGLE,
                "gnome_shell_extensions_proxy",
                return_value=proxy,
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "extension_info",
                return_value={"enabled": True, "state": 1, "error": ""},
            ),
            mock.patch.object(POWER_TOGGLE, "request_extension_enabled") as request,
        ):
            self.assertTrue(POWER_TOGGLE.set_extension_enabled(True))

        request.assert_not_called()

    def test_failed_enable_is_retryable_failure(self) -> None:
        proxy = mock.Mock()
        with (
            mock.patch.object(POWER_TOGGLE, "extension_is_enabled", return_value=False),
            mock.patch.object(
                POWER_TOGGLE,
                "gnome_shell_extensions_proxy",
                return_value=proxy,
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "extension_info",
                return_value={"enabled": False, "state": 2, "error": ""},
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "request_extension_enabled",
                return_value=False,
            ),
            self.assertLogs("power-toggle", level="ERROR"),
        ):
            self.assertFalse(POWER_TOGGLE.set_extension_enabled(True))

    def test_runtime_active_with_disabled_setting_resets_manager(self) -> None:
        proxy = mock.Mock()
        with (
            mock.patch.object(POWER_TOGGLE, "extension_is_enabled", return_value=False),
            mock.patch.object(
                POWER_TOGGLE,
                "gnome_shell_extensions_proxy",
                return_value=proxy,
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "extension_info",
                return_value={"enabled": False, "state": 1, "error": ""},
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "request_extension_enabled",
                return_value=True,
            ) as request,
            mock.patch.object(
                POWER_TOGGLE,
                "wait_for_extension_state",
                side_effect=(False, True),
            ) as wait,
            mock.patch.object(
                POWER_TOGGLE,
                "wait_for_extension_configuration",
                return_value=True,
            ) as wait_configuration,
            self.assertLogs("power-toggle", level="WARNING"),
        ):
            self.assertTrue(POWER_TOGGLE.set_extension_enabled(False))

        self.assertEqual(
            request.call_args_list,
            [mock.call(proxy, True), mock.call(proxy, False)],
        )
        self.assertEqual(
            wait.call_args_list,
            [
                mock.call(proxy, False, log_failure=False),
                mock.call(proxy, False),
            ],
        )
        wait_configuration.assert_called_once_with(proxy, True)


class ExtensionRuntimeTests(unittest.TestCase):
    def test_reads_shell_runtime_state(self) -> None:
        result = mock.Mock()
        result.unpack.return_value = (
            {
                "uuid": POWER_TOGGLE.EXTENSION_UUID,
                "enabled": False,
                "state": 2.0,
                "error": "",
            },
        )
        proxy = mock.Mock()
        proxy.call_sync.return_value = result

        self.assertEqual(
            POWER_TOGGLE.extension_info(proxy),
            {"enabled": False, "state": 2, "error": ""},
        )
        self.assertEqual(proxy.call_sync.call_args.args[0], "GetExtensionInfo")

    def test_rejects_invalid_shell_runtime_state(self) -> None:
        result = mock.Mock()
        result.unpack.return_value = (
            {
                "uuid": POWER_TOGGLE.EXTENSION_UUID,
                "enabled": False,
                "state": True,
                "error": "",
            },
        )
        proxy = mock.Mock()
        proxy.call_sync.return_value = result

        with self.assertRaisesRegex(RuntimeError, "invalid extension state"):
            POWER_TOGGLE.extension_info(proxy)

    def test_battery_reconcile_only_for_enabled_or_active_state(self) -> None:
        cases = (
            (False, False, 2, False),
            (True, False, 2, True),
            (False, True, 2, True),
            (False, False, 1, True),
            (False, False, 7, False),
        )
        for configured, manager_enabled, runtime_state, expected in cases:
            with (
                self.subTest(
                    configured=configured,
                    manager_enabled=manager_enabled,
                    runtime_state=runtime_state,
                ),
                mock.patch.object(
                    POWER_TOGGLE,
                    "extension_is_enabled",
                    return_value=configured,
                ),
                mock.patch.object(
                    POWER_TOGGLE,
                    "extension_info",
                    return_value={
                        "enabled": manager_enabled,
                        "state": runtime_state,
                        "error": "",
                    },
                ),
            ):
                self.assertEqual(
                    POWER_TOGGLE.extension_needs_battery_reconcile(mock.Mock()),
                    expected,
                )


class MonitorTests(DesktopTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.power_proxy = mock.Mock()
        self.extension_proxy = mock.Mock()
        self.power_proxy.get_cached_property.return_value = POWER_TOGGLE.GLib.Variant(
            "b", False
        )
        self.retry_timer = mock.Mock(return_value=42)
        self.cancel_timer = mock.Mock()
        patches = (
            mock.patch.object(
                POWER_TOGGLE,
                "acquire_monitor_lock",
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "upower_proxy",
                return_value=self.power_proxy,
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "gnome_shell_extensions_proxy",
                return_value=self.extension_proxy,
            ),
            mock.patch.object(POWER_TOGGLE.GLib, "MainLoop"),
            mock.patch.object(POWER_TOGGLE.GLibUnix, "signal_add"),
            mock.patch.object(
                POWER_TOGGLE.GLib, "timeout_add_seconds", self.retry_timer
            ),
            mock.patch.object(POWER_TOGGLE.GLib, "source_remove", self.cancel_timer),
        )
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def emit(self, proxy: mock.Mock, signal_name: str, *args: object) -> None:
        callbacks = [
            call.args[1]
            for call in proxy.connect.call_args_list
            if call.args[0] == signal_name
        ]
        self.assertEqual(len(callbacks), 1)
        callbacks[0](proxy, *args)

    def power_changed(self, using_battery: bool) -> None:
        self.power_proxy.get_cached_property.return_value = POWER_TOGGLE.GLib.Variant(
            "b", using_battery
        )
        self.emit(
            self.power_proxy,
            "g-properties-changed",
            POWER_TOGGLE.GLib.Variant(
                "a{sv}", {"OnBattery": POWER_TOGGLE.GLib.Variant("b", using_battery)}
            ),
            [],
        )

    def assert_failed_transition_recovers(self, initial_battery: bool) -> None:
        baseline = POWER_TOGGLE.state_snapshot()
        self.power_proxy.get_cached_property.return_value = POWER_TOGGLE.GLib.Variant(
            "b", initial_battery
        )
        self.assertEqual(POWER_TOGGLE.monitor(), 0)
        self.retry_timer.assert_not_called()

        POWER_TOGGLE.set_keyboard_backlights.side_effect = lambda *_: False
        with mock.patch.object(POWER_TOGGLE.LOG, "error"):
            self.power_changed(not initial_battery)
        self.assertEqual(
            self.desktop, {"extension": initial_battery, "seconds": initial_battery}
        )
        self.assertEqual(POWER_TOGGLE.load_saved_state(), baseline)
        self.retry_timer.assert_called_once_with(POWER_TOGGLE.RETRY_SECONDS, mock.ANY)

        POWER_TOGGLE.set_keyboard_backlights.side_effect = self.set_keyboard_backlights
        self.power_changed(initial_battery)
        self.assertEqual(
            self.desktop,
            {"extension": not initial_battery, "seconds": not initial_battery},
        )
        self.assertEqual(
            self.keyboard_backlights, {self.keyboard_path: 0 if initial_battery else 2}
        )
        self.assertEqual(self.gnome_keyboard_percentage, 0 if initial_battery else 100)
        self.assertEqual(
            POWER_TOGGLE.load_saved_state(), baseline if initial_battery else None
        )
        self.cancel_timer.assert_called_once_with(42)

        POWER_TOGGLE.set_extension_enabled.reset_mock()
        self.power_changed(initial_battery)
        POWER_TOGGLE.set_extension_enabled.assert_not_called()
        self.retry_timer.assert_called_once()

    def test_ac_return_after_partial_battery_failure_restores_baseline(self) -> None:
        self.assert_failed_transition_recovers(initial_battery=False)

    def test_battery_return_after_partial_restore_reapplies_policy(self) -> None:
        self.assert_failed_transition_recovers(initial_battery=True)

    def test_failed_forced_reconcile_retries_unchanged_power_source(self) -> None:
        self.power_proxy.get_cached_property.return_value = POWER_TOGGLE.GLib.Variant(
            "b", True
        )
        self.assertEqual(POWER_TOGGLE.monitor(), 0)
        baseline = POWER_TOGGLE.load_saved_state()
        self.keyboard_backlights[self.keyboard_path] = 2
        self.gnome_keyboard_percentage = 100
        POWER_TOGGLE.set_keyboard_backlights.side_effect = lambda *_: False
        self.emit(self.extension_proxy, "notify::g-name-owner", None)
        self.retry_timer.assert_called_once_with(POWER_TOGGLE.RETRY_SECONDS, mock.ANY)
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 2})

        POWER_TOGGLE.set_keyboard_backlights.reset_mock()
        POWER_TOGGLE.set_keyboard_backlights.side_effect = self.set_keyboard_backlights
        retry = self.retry_timer.call_args.args[1]
        self.assertEqual(retry(), POWER_TOGGLE.GLib.SOURCE_REMOVE)
        POWER_TOGGLE.set_keyboard_backlights.assert_called_once_with(
            {self.keyboard_path: 0}, 0
        )
        self.assertEqual(self.keyboard_backlights, {self.keyboard_path: 0})
        self.assertEqual(self.gnome_keyboard_percentage, 0)
        self.assertEqual(POWER_TOGGLE.load_saved_state(), baseline)
        self.retry_timer.assert_called_once()
        self.cancel_timer.assert_not_called()

        POWER_TOGGLE.set_keyboard_backlights.reset_mock()
        self.power_changed(True)
        POWER_TOGGLE.set_keyboard_backlights.assert_not_called()
        self.retry_timer.assert_called_once()

    def test_target_extension_state_change_forces_reconciliation(self) -> None:
        self.power_proxy.get_cached_property.return_value = POWER_TOGGLE.GLib.Variant(
            "b", True
        )
        with (
            mock.patch.object(
                POWER_TOGGLE,
                "apply_current_power_state",
                return_value=True,
            ) as apply,
            mock.patch.object(
                POWER_TOGGLE,
                "extension_needs_battery_reconcile",
                side_effect=(False, True),
            ) as needs_reconcile,
        ):
            self.assertEqual(POWER_TOGGLE.monitor(), 0)
            apply.reset_mock()
            parameters = mock.Mock()
            parameters.unpack.return_value = ("another-extension@example.com", {})
            self.emit(
                self.extension_proxy,
                "g-signal",
                None,
                "ExtensionStateChanged",
                parameters,
            )
            apply.assert_not_called()

            parameters.unpack.return_value = (POWER_TOGGLE.EXTENSION_UUID, {})
            self.emit(
                self.extension_proxy,
                "g-signal",
                None,
                "ExtensionStateChanged",
                parameters,
            )
            apply.assert_not_called()
            self.emit(
                self.extension_proxy,
                "g-signal",
                None,
                "ExtensionStateChanged",
                parameters,
            )
            apply.assert_called_once_with(self.power_proxy)
            self.assertEqual(needs_reconcile.call_count, 2)


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

    def test_derives_gnome_percentage_from_saved_hardware_level(self) -> None:
        proxy = mock.Mock()
        proxy.call_sync.return_value = POWER_TOGGLE.GLib.Variant("(i)", (3,))

        with (
            mock.patch.object(
                POWER_TOGGLE, "keyboard_backlight_paths", return_value=[self.PATH]
            ),
            mock.patch.object(
                POWER_TOGGLE, "keyboard_backlight_proxy", return_value=proxy
            ),
        ):
            percentage = POWER_TOGGLE.keyboard_backlight_percentage(
                {self.PATH: 2}
            )

        self.assertEqual(percentage, 67)
        self.assertEqual(proxy.call_sync.call_args.args[0], "GetMaxBrightness")

    def test_empty_backlight_state_has_no_gnome_percentage(self) -> None:
        with mock.patch.object(POWER_TOGGLE, "keyboard_backlight_paths") as paths:
            self.assertIsNone(POWER_TOGGLE.keyboard_backlight_percentage({}))

        paths.assert_not_called()

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

    def test_updates_gnome_before_restoring_exact_hardware_level(self) -> None:
        mutations = mock.Mock()
        mutations.gnome.return_value = True
        mutations.upower.return_value = True

        with (
            mock.patch.object(
                POWER_TOGGLE,
                "set_gnome_keyboard_backlight",
                side_effect=mutations.gnome,
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "set_keyboard_backlight",
                side_effect=mutations.upower,
            ),
        ):
            self.assertTrue(
                POWER_TOGGLE.set_keyboard_backlights({self.PATH: 2}, 100)
            )

        self.assertEqual(
            mutations.mock_calls,
            [mock.call.gnome(100), mock.call.upower(self.PATH, 2)],
        )

    def test_gnome_failure_still_applies_exact_hardware_level(self) -> None:
        mutations = mock.Mock()
        mutations.gnome.return_value = False
        mutations.upower.return_value = True

        with (
            mock.patch.object(
                POWER_TOGGLE,
                "set_gnome_keyboard_backlight",
                side_effect=mutations.gnome,
            ),
            mock.patch.object(
                POWER_TOGGLE,
                "set_keyboard_backlight",
                side_effect=mutations.upower,
            ),
        ):
            self.assertFalse(
                POWER_TOGGLE.set_keyboard_backlights({self.PATH: 2}, 100)
            )

        self.assertEqual(
            mutations.mock_calls,
            [mock.call.gnome(100), mock.call.upower(self.PATH, 2)],
        )


class GnomeKeyboardBacklightMutationTests(unittest.TestCase):
    def test_sets_property_even_when_cached_percentage_may_match(self) -> None:
        proxy = mock.Mock()
        proxy.call_sync.side_effect = (
            POWER_TOGGLE.GLib.Variant("()", ()),
            POWER_TOGGLE.GLib.Variant(
                "(v)", (POWER_TOGGLE.GLib.Variant("i", 0),)
            ),
        )

        with mock.patch.object(
            POWER_TOGGLE, "gnome_keyboard_backlight_proxy", return_value=proxy
        ):
            self.assertTrue(POWER_TOGGLE.set_gnome_keyboard_backlight(0))

        self.assertEqual(
            [call.args[0] for call in proxy.call_sync.call_args_list],
            [
                "org.freedesktop.DBus.Properties.Set",
                "org.freedesktop.DBus.Properties.Get",
            ],
        )
        self.assertEqual(
            proxy.call_sync.call_args_list[0].args[1].unpack(),
            (
                POWER_TOGGLE.GSD_POWER_KEYBOARD_INTERFACE,
                "Brightness",
                0,
            ),
        )

    def test_failed_property_verification_is_retryable_failure(self) -> None:
        proxy = mock.Mock()
        proxy.call_sync.side_effect = (
            POWER_TOGGLE.GLib.Variant("()", ()),
            POWER_TOGGLE.GLib.Variant(
                "(v)", (POWER_TOGGLE.GLib.Variant("i", 100),)
            ),
        )

        with (
            mock.patch.object(
                POWER_TOGGLE, "gnome_keyboard_backlight_proxy", return_value=proxy
            ),
            self.assertLogs("power-toggle", level="ERROR"),
        ):
            self.assertFalse(POWER_TOGGLE.set_gnome_keyboard_backlight(0))


if __name__ == "__main__":
    unittest.main()
