# Power Toggle

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
/usr/bin/bash -n install.sh uninstall.sh
```
