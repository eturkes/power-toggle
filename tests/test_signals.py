from __future__ import annotations

import signal
import subprocess
import sys
import unittest

from test_power_toggle import ROOT


SIGNAL_PROBE = """
import os
import signal
import sys
from unittest import mock

sys.path.insert(0, 'tests')
from test_power_toggle import POWER_TOGGLE
from test_hardware import HARDWARE

target, signum = sys.argv[1], int(sys.argv[2])

def terminate():
    os.kill(os.getpid(), signum)
    return False

POWER_TOGGLE.GLib.timeout_add(10, terminate)
if target == 'desktop':
    with (
        mock.patch.object(POWER_TOGGLE, 'acquire_monitor_lock'),
        mock.patch.object(POWER_TOGGLE, 'upower_proxy'),
        mock.patch.object(POWER_TOGGLE, 'gnome_shell_extensions_proxy'),
        mock.patch.object(POWER_TOGGLE, 'on_battery', return_value=True),
        mock.patch.object(POWER_TOGGLE, 'apply_current_power_state',
                          return_value=POWER_TOGGLE.PolicyResult.COMPLETE),
    ):
        assert POWER_TOGGLE.monitor() == 0
else:
    with (
        mock.patch.object(HARDWARE, 'Properties'),
        mock.patch.object(HARDWARE.Monitor, 'reconcile', return_value=False),
    ):
        assert HARDWARE.Monitor(mock.Mock(), mock.Mock()).run() == 0
"""


class SignalTests(unittest.TestCase):
    def check_signals(self, target):
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(target=target, signal=signum):
                result = subprocess.run(
                    [sys.executable, "-c", SIGNAL_PROBE, target, str(signum)],
                    cwd=ROOT, capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_desktop_monitor_stops_on_native_signals(self):
        self.check_signals("desktop")

    def test_hardware_monitor_stops_on_native_signals(self):
        self.check_signals("hardware")
