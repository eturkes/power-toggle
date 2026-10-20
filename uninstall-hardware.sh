#!/usr/bin/bash
set -euo pipefail

sudo /usr/bin/systemctl disable --now power-toggle-hardware.service
sudo /usr/bin/python3 - <<'PY'
from pathlib import Path
for path in Path("/sys/class/drm").glob("card*/device/tile*/gt*/freq0/power_profile"):
    path.write_text("base\n")
boost = Path("/sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost")
if boost.exists():
    boost.write_text("0\n")
for path in (Path("/usr/local/libexec/power-toggle-hardware"),
             Path("/etc/systemd/system/power-toggle-hardware.service")):
    path.unlink(missing_ok=True)
PY
sudo /usr/bin/systemctl daemon-reload
/usr/bin/powerprofilesctl set balanced
printf 'Removed hardware switching. Intel P-state remains in active mode.\n'
printf 'Enable your preferred automatic profile selector if needed.\n'
