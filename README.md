# Power Toggle

`power-toggle` watches UPower and adjusts desktop state when the power source
changes:

- On battery: disable `system-monitor-next@paradoxxx.zero.gmail.com` and hide
  seconds in the GNOME clock, then turn off every keyboard backlight reported
  by UPower.
- On external power: restore all managed values to exactly how they were before
  the switch to battery.

The pre-battery values are saved under
`~/.local/state/power-toggle/` (or `$XDG_STATE_HOME/power-toggle/`). This means a
logout, reboot, or watcher restart while on battery does not overwrite the
values that need to be restored.

The watcher is event-driven: it sleeps until UPower reports a change. A
30-second timer is created only after an action fails, then removed after a
successful retry.

## Requirements

- GNOME Shell with `system-monitor-next@paradoxxx.zero.gmail.com` installed
- UPower with `org.freedesktop.UPower.EnumerateKbdBacklights`
- System Python 3 with PyGObject (`Gio`, `GLib`, and `GLibUnix`)
- `gnome-extensions` and a systemd user manager

## Try it

Show the current source and managed settings without changing anything:

```sh
./power-toggle status
```

Apply the policy once and exit:

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

## Run automatically after login

```sh
./install.sh
```

Inspect its logs with:

```sh
journalctl --user -u power-toggle.service
```

Remove the service and restore any saved pre-battery state with:

```sh
./uninstall.sh
```

## Development

Run the isolated state-machine tests and shell syntax checks:

```sh
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/bash -n install.sh uninstall.sh
```
