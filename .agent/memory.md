# Power Toggle memory

- Runtime = system `/usr/bin/python3` + PyGObject/GIO → host-native GNOME/D-Bus
  APIs; zero textual D-Bus parsing or added package/build surface. Contracts =
  [UPower](https://upower.freedesktop.org/docs/UPower/) + [Gio proxy
  cache](https://docs.gtk.org/gio/class.DBusProxy.html) + [property-change
  signal](https://docs.gtk.org/gio/signal.DBusProxy.g-properties-changed.html).
- Host diagnostics = `/usr/bin/gsettings` + `/usr/bin/gdbus`; Linuxbrew PATH
  shadows both and can observe the wrong buses/schemas.
- State invariant = capture one baseline before battery mutations → atomic JSON
  under `$XDG_STATE_HOME/power-toggle/` → retain through restart/retry until
  complete restoration.
- Keyboard invariant = persist native per-device levels + GNOME menu percentage;
  set `org.gnome.SettingsDaemon.Power.Keyboard` first for Shell's
  `PropertiesChanged`, then UPower devices for exact levels. GSD ignores UPower
  changes sourced `external`.
