from __future__ import annotations

import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader(
    "hardware_under_test", str(ROOT / "power-toggle-hardware")
)
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
HARDWARE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(HARDWARE)


class HardwareTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix=".test-state-", dir=ROOT)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pstate = self.root / "devices/system/cpu/intel_pstate"
        self.cpu_root = self.root / "devices/system/cpu/cpufreq"
        self.gpu_root = self.root / "class/drm/card0/device/tile0"
        self.battery = True
        self.profile = "power-saver"
        for name, value in (
            ("status", "active"), ("no_turbo", "0"), ("max_perf_pct", "100"),
            ("hwp_dynamic_boost", "0"),
        ):
            self.put(self.pstate / name, value)
        for index in range(8):
            cpu = self.cpu_root / f"policy{index}"
            for name, value in (
                ("scaling_governor", "powersave"),
                ("energy_performance_preference", "power"),
                ("scaling_min_freq", "400000"),
                ("scaling_max_freq", "5000000" if index < 4 else "3700000"),
                ("cpuinfo_max_freq", "5000000" if index < 4 else "3700000"),
            ):
                self.put(cpu / name, value)
        for index, maximum in ((0, "2000"), (1, "1200")):
            for name, value in (
                ("power_profile", "base [power_saving]"),
                ("min_freq", "800" if index == 0 else "400"),
                ("max_freq", maximum), ("rp0_freq", maximum),
            ):
                self.put(self.gpu_root / f"gt{index}/freq0" / name, value)
        self.put(self.root / "firmware/acpi/platform_profile", "low-power")
        self.upower = mock.Mock()
        self.upower.get.side_effect = lambda name: self.battery
        self.ppd = mock.Mock()
        self.ppd.get.side_effect = lambda name: self.profile
        self.ppd.set_profile.side_effect = self.set_profile
        self.monitor = HARDWARE.Monitor(self.upower, self.ppd, self.root)
        self.idle = mock.patch.object(HARDWARE.GLib, "idle_add").start()
        self.timer = mock.patch.object(HARDWARE.GLib, "timeout_add_seconds").start()
        self.remove = mock.patch.object(HARDWARE.GLib, "source_remove").start()
        self.addCleanup(mock.patch.stopall)

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value + "\n")

    def set_profile(self, profile):
        self.profile = profile
        battery = profile == "power-saver"
        for cpu in self.cpu_root.glob("policy*"):
            self.put(cpu / "energy_performance_preference",
                     "power" if battery else "performance")
        self.put(self.root / "firmware/acpi/platform_profile",
                 "low-power" if battery else "performance")

    def report(self):
        return HARDWARE.status(self.upower, self.ppd, self.root)

    def test_ac_battery_ac_updates_all_engines_and_cpu_preferences(self):
        for battery in (False, True, False):
            with self.subTest(battery=battery):
                self.battery = battery
                self.monitor.reconcile()
                report = self.report()
                self.assertEqual(report["issues"], [])
                self.assertEqual(report["profile"],
                                 "power-saver" if battery else "performance")
                self.assertEqual({cpu["epp"] for cpu in report["cpus"]},
                                 {"power" if battery else "performance"})
                self.assertEqual({gpu["profile"] for gpu in report["gpus"]},
                                 {"power_saving" if battery else "base"})
                self.assertEqual(report["hwp_dynamic_boost"], "0" if battery else "1")
        self.timer.assert_not_called()

    def test_ac_removes_stale_software_caps_without_changing_hardware_limits(self):
        self.battery = False
        self.put(self.pstate / "no_turbo", "1")
        self.put(self.pstate / "max_perf_pct", "50")
        for cpu in self.cpu_root.glob("policy*"):
            self.put(cpu / "scaling_max_freq", "1800000")
        for gpu in self.gpu_root.glob("gt*/freq0"):
            self.put(gpu / "max_freq", "900")
        self.monitor.reconcile()
        report = self.report()
        self.assertEqual(report["issues"], [])
        self.assertTrue(report["turbo_allowed"])
        self.assertEqual(report["max_perf_pct"], "100")
        self.assertEqual([g["hardware_max_mhz"] for g in report["gpus"]], [2000, 1200])

    def test_settled_policy_has_no_timer_or_redundant_sysfs_writes(self):
        with mock.patch.object(Path, "write_text", side_effect=AssertionError("write")):
            self.monitor.reconcile()
            self.monitor.reconcile()
        self.ppd.set_profile.assert_not_called()
        self.timer.assert_not_called()
        self.idle.assert_not_called()

    def test_unknown_power_source_never_selects_ac(self):
        self.battery = None
        with mock.patch.object(Path, "write_text", side_effect=AssertionError("write")):
            with self.assertLogs("power-toggle-hardware", level="WARNING"):
                self.monitor.reconcile()
        self.ppd.set_profile.assert_not_called()
        self.timer.assert_called_once()
        self.assertIsNone(self.monitor.last_source)

    def test_service_outage_waits_without_mutating_policy(self):
        self.upower.get.side_effect = RuntimeError("UPower is unavailable")
        with mock.patch.object(Path, "write_text", side_effect=AssertionError("write")):
            with self.assertLogs("power-toggle-hardware", level="WARNING"):
                self.monitor.reconcile()
                self.monitor.reconcile()
        self.timer.assert_called_once()
        self.ppd.set_profile.assert_not_called()

    def test_partial_gpu_failure_then_power_reversal_reconciles_all_devices(self):
        self.battery = False
        original = HARDWARE.write
        failed_path = self.gpu_root / "gt1/freq0/power_profile"

        def fail_one(path, value):
            if path == failed_path:
                raise OSError("temporary GPU error")
            original(path, value)

        with mock.patch.object(HARDWARE, "write", side_effect=fail_one):
            with self.assertLogs("power-toggle-hardware", level="WARNING"):
                self.monitor.reconcile()
        self.assertEqual(HARDWARE.read(self.gpu_root / "gt0/freq0/power_profile"), "base")
        self.assertIsNone(self.monitor.last_source)
        self.timer.assert_called_once()
        self.battery = True
        self.monitor.reconcile()
        self.assertEqual(self.report()["issues"], [])
        self.assertIsNone(self.monitor.retry_source)
        self.remove.assert_called_once()

    def test_retry_recovers_when_gpu_returns(self):
        gpu = self.gpu_root / "gt1/freq0/power_profile"
        gpu.unlink()
        self.battery = False
        self.monitor.reconcile()
        # A GPU added later is picked up on resume rather than cached forever.
        self.put(gpu, "base [power_saving]")
        self.monitor.resumed(None, None, "PrepareForSleep",
                             HARDWARE.GLib.Variant("(b)", (False,)))
        self.idle.assert_called_once()
        self.monitor.reconcile()
        self.assertEqual(self.report()["issues"], [])
        self.assertEqual(HARDWARE.read(gpu), "base")

    def test_passive_mode_is_reported_instead_of_claiming_success(self):
        self.put(self.pstate / "status", "passive")
        with self.assertLogs("power-toggle-hardware", level="WARNING"):
            self.monitor.reconcile()
        self.timer.assert_called_once()
        self.assertTrue(self.report()["issues"])

    def test_every_core_is_checked(self):
        self.put(self.cpu_root / "policy7/energy_performance_preference",
                 "balance_performance")
        self.assertEqual(self.report()["issues"],
                         ["policy7: CPU energy preference is incorrect"])

    def test_profile_notifications_do_not_create_a_feedback_loop(self):
        changed = HARDWARE.GLib.Variant("a{sv}", {
            "ActiveProfile": HARDWARE.GLib.Variant("s", "power-saver"),
        })
        self.monitor.profile_changed(None, changed, [])
        self.idle.assert_not_called()
        self.profile = "balanced"
        self.monitor.profile_changed(None, changed, [])
        self.monitor.profile_changed(None, changed, [])
        self.idle.assert_called_once()

    def test_only_source_changes_and_resume_trigger_reconciliation(self):
        self.monitor.power_changed(
            None, HARDWARE.GLib.Variant("a{sv}", {
                "LidIsClosed": HARDWARE.GLib.Variant("b", False),
            }), [],
        )
        self.monitor.resumed(None, None, "PrepareForSleep",
                             HARDWARE.GLib.Variant("(b)", (True,)))
        self.idle.assert_not_called()
        self.monitor.power_changed(None, HARDWARE.GLib.Variant("a{sv}", {}),
                                   ["OnBattery"])
        self.idle.assert_called_once()

    def test_source_change_during_apply_queues_new_policy_without_stale_success(self):
        self.battery = False
        original = HARDWARE.configure_hardware

        def reverse_source(battery, root):
            original(battery, root)
            self.battery = True

        with mock.patch.object(HARDWARE, "configure_hardware", side_effect=reverse_source):
            self.monitor.reconcile()
        self.assertIsNone(self.monitor.last_source)
        self.idle.assert_called_once()
        self.monitor.reconcile()
        self.assertEqual(self.report()["issues"], [])


if __name__ == "__main__":
    unittest.main()
