#!/usr/bin/bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
binary_dir="${HOME}/.local/bin"
user_unit_dir=${XDG_CONFIG_HOME:-"${HOME}/.config"}/systemd/user
installed_binary="$binary_dir/power-toggle"
installed_unit="$user_unit_dir/power-toggle.service"

/usr/bin/systemctl --user disable --now power-toggle.service 2>/dev/null || true

if [[ -x "$installed_binary" ]]; then
    "$installed_binary" restore
else
    "$project_dir/power-toggle" restore
fi

/usr/bin/rm -f -- "$installed_binary" "$installed_unit"
/usr/bin/systemctl --user daemon-reload

printf 'Stopped and removed power-toggle.service and restored saved GNOME state\n'
