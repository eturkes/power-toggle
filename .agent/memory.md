# Power Toggle - project memory

- Scope = personal GNOME user-session policy: battery → disable
  `system-monitor-next@paradoxxx.zero.gmail.com` + clock seconds + all UPower
  keyboard backlights; external power → restore the exact captured values.
- Runtime = system `/usr/bin/python3` + PyGObject/GIO. Rationale: host-native
  GNOME binding, cached D-Bus properties/signals, no textual D-Bus parsing or
  added build/package surface. Contracts: [UPower
  interface](https://upower.freedesktop.org/docs/UPower/), [Gio proxy
  cache](https://docs.gtk.org/gio/class.DBusProxy.html), [property-change
  signal](https://docs.gtk.org/gio/signal.DBusProxy.g-properties-changed.html).
- Host PATH caveat = Linuxbrew shadows `gsettings`/`gdbus`; diagnostics must use
  `/usr/bin/...` to observe the live GNOME/system buses and schemas.
- State invariant = capture once before battery mutations; atomic JSON under
  `$XDG_STATE_HOME/power-toggle/`; retain until complete restoration. Restarting
  on battery must preserve the original baseline.
- Keyboard invariant = state stores native per-device levels + GNOME's menu
  percentage. Mutate `org.gnome.SettingsDaemon.Power.Keyboard` first so Shell
  receives `PropertiesChanged`, then every enumerated UPower device to preserve
  exact levels. GSD intentionally ignores UPower changes sourced `external`.
- Monitor invariant = UPower signal-driven steady state; retry timer exists only
  after failure. Extension CLI subprocesses run only when its desired state
  differs.
- Verification = `/usr/bin/python3 -m unittest discover -s tests -v` +
  `/usr/bin/bash -n install.sh uninstall.sh`; `./power-toggle status` is the
  live, read-only integration smoke test.
- Install = `./install.sh` copies into user-local bin/unit paths and starts the
  graphical-session service; `./uninstall.sh` stops it, restores saved state,
  then removes installed files.
