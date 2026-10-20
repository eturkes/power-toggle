#!/usr/bin/bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
extension=auto-power-profile@dmy3k.github.io

if (( EUID == 0 )); then
    printf 'Run this installer as the desktop user. It uses sudo for system changes.\n' >&2
    exit 1
fi

# Validate host support before changing either policy owner.
test -e /sys/devices/system/cpu/intel_pstate/status
test -x /usr/bin/sdbootutil
/usr/bin/python3 - <<'PY'
from pathlib import Path
from gi.repository import Gio
assert list(Path("/sys/class/drm").glob("card*/device/tile*/gt*/freq0/power_profile"))
PY

sudo /usr/bin/install -d -m 0755 /usr/local/libexec
sudo /usr/bin/install -m 0755 "$project_dir/power-toggle-hardware" /usr/local/libexec/power-toggle-hardware
sudo /usr/bin/install -m 0644 "$project_dir/power-toggle-hardware.service" /etc/systemd/system/power-toggle-hardware.service

sudo /usr/bin/python3 - <<'PY'
from pathlib import Path
path = Path("/etc/kernel/cmdline")
text = path.read_text()
tokens = text.split()
unsupported = [v for v in tokens if v.startswith("intel_pstate=")
               and v not in ("intel_pstate=active", "intel_pstate=passive")]
if unsupported:
    raise SystemExit(f"Resolve incompatible Intel P-state options first: {unsupported}")
if "intel_pstate=passive" in tokens:
    path.write_text(text.replace("intel_pstate=passive", "intel_pstate=active"))
elif "intel_pstate=active" not in tokens:
    path.write_text(text.rstrip() + " intel_pstate=active\n")
PY
sudo /usr/bin/sdbootutil update-all-entries

# One system-wide selector owns profiles, including outside a desktop session.
if /usr/bin/gnome-extensions info "$extension" >/dev/null 2>&1; then
    /usr/bin/gnome-extensions disable "$extension"
fi
sudo /usr/bin/python3 - <<'PY'
from pathlib import Path
path = Path("/sys/devices/system/cpu/intel_pstate/status")
if path.read_text().strip() != "active":
    path.write_text("active\n")
PY
sudo /usr/bin/systemctl restart power-profiles-daemon.service
sudo /usr/bin/systemctl daemon-reload
sudo /usr/bin/systemctl enable power-toggle-hardware.service
sudo /usr/bin/systemctl restart power-toggle-hardware.service
printf 'Installed system-wide CPU/GPU switching. No reboot is required.\n'
printf 'Check the policy: /usr/local/libexec/power-toggle-hardware status\n'
