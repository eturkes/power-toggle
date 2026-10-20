# Power Toggle

Power Toggle provides separate desktop and Intel hardware policies.
The desktop watcher runs in the user session. The optional hardware watcher
runs as a system service.

## CPU and GPU policy

The hardware watcher selects these policies:

| Setting | AC | Battery |
| --- | --- | --- |
| Power profile | `performance` | `power-saver` |
| Intel CPU EPP | `performance` | `power` |
| Lenovo platform profile | `performance` | `low-power` |
| HWP dynamic boost | Enabled | Disabled |
| Intel Xe GPU profile, every engine | `base` | `power_saving` |

Intel P-state uses active HWP mode. Power Profiles Daemon owns CPU EPP and
the platform profile. Its `powersave` governor still permits full performance
with EPP `performance`; it does not fix the CPU at its minimum frequency.
See the [CPU driver documentation](https://docs.kernel.org/admin-guide/pm/intel_pstate.html)
and the [Xe power-profile implementation](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/xe/xe_guc_pc.c).

AC transitions restore CPU turbo, the full CPU performance range, and each
CPU/GPU hardware frequency ceiling. Firmware thermal and power limits remain
intact. Battery mode uses energy-saving scaling without fixed frequency caps
or disabling turbo. GPU frequency floors retain their driver defaults.

The hardware watcher handles power-source changes, daemon restarts, and resume.
It does not poll after applying a policy. Failed operations retry after
30 seconds. Manual power-profile changes are reconciled to the current power
source while this service runs.

### Install hardware switching

This installer targets Aeon with `sdbootutil`, Intel HWP, Intel Xe graphics,
UPower, Power Profiles Daemon, and system PyGObject.

Run as the desktop user:

```sh
./install-hardware.sh
```

The installer uses `sudo` for system changes. It sets `intel_pstate=active`
in `/etc/kernel/cmdline` and updates the current snapshot's boot entries.
It also applies active mode immediately and restarts Power Profiles Daemon.
No reboot is required.

The installer disables `auto-power-profile@dmy3k.github.io`. The system service
replaces that extension's profile selection and remains active outside the
desktop session. The desktop watcher below remains separate.

Check the live policy:

```sh
/usr/local/libexec/power-toggle-hardware status
systemctl status power-toggle-hardware.service
journalctl -u power-toggle-hardware.service
```

The status command checks every CPU policy and Xe engine.
It exits nonzero if the hardware policy does not match the power source.

To remove hardware switching:

```sh
./uninstall-hardware.sh
```

Removal selects Balanced, restores the GPU base profile, and disables HWP
dynamic boost. Active Intel P-state mode remains enabled.
If required, restore the desktop profile selector:

```sh
gnome-extensions enable auto-power-profile@dmy3k.github.io
```

## Desktop policy

`power-toggle` watches UPower and changes desktop settings when the power source
changes:

- On battery power, it disables `system-monitor-next@paradoxxx.zero.gmail.com`
  and hides seconds in the GNOME clock. It turns off every keyboard backlight
  that UPower reports. It also synchronizes the GNOME keyboard-backlight quick
  setting.
- On external power, it restores the saved extension setting, clock setting,
  and keyboard backlight levels. It sets the GNOME keyboard-backlight quick
  setting to the percentage derived from the saved hardware level.

`power-toggle` stores the pre-battery values under
`~/.local/state/power-toggle/` (or `$XDG_STATE_HOME/power-toggle/`). A logout,
reboot, or watcher restart on battery power does not replace these values.

While the lid is closed, the watcher defers keyboard changes and keeps the
saved baseline. Extension and clock changes continue. When the lid opens,
the watcher applies the keyboard policy for the current power source.
A closed lid alone does not start a retry timer.

The watcher responds to UPower power-source and lid-state changes, and managed
GNOME Shell extension-state changes. It corrects an extension that activates
late during GNOME Shell startup. It creates a 30-second timer only after an
action fails. It removes the timer after a successful retry.

## Requirements

- GNOME Shell with `system-monitor-next@paradoxxx.zero.gmail.com` installed
- UPower with `org.freedesktop.UPower.EnumerateKbdBacklights`
- System Python 3 with PyGObject (`Gio`, `GLib`, and `GLibUnix`)
- `gnome-extensions` and a systemd user manager

## Try it

Display the current power source and managed settings without changing the
desktop:

```sh
./power-toggle status
```

The output shows the lid state and separates the configured extension state
from the live runtime state. It also shows each UPower hardware level and the
cached percentage for the GNOME keyboard-backlight quick setting. These values
expose configuration, runtime, desktop, and hardware mismatches.

Apply the policy one time:

```sh
./power-toggle once
```

Watch for changes in the foreground:

```sh
./power-toggle monitor
```

Press `Ctrl+C` to stop the foreground watcher. If it was stopped on battery,
restore the saved settings with:

```sh
./power-toggle restore
```

If `once` or `restore` defers a keyboard change, it exits with status 1.
Open the lid and run the command again.

## Run automatically after login

```sh
./install.sh
```

Inspect the service logs:

```sh
journalctl --user -u power-toggle.service
```

Run the uninstall script:

```sh
./uninstall.sh
```

The script removes the service and restores any saved pre-battery state.

## Development

Run the development checks:

```sh
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/bash -n install.sh uninstall.sh install-hardware.sh uninstall-hardware.sh
```

After installation, verify the system unit:

```sh
systemd-analyze verify power-toggle-hardware.service
```

Connect AC and run the hardware status command. Disconnect AC and run it
again. Both results must have an empty `issues` list.
