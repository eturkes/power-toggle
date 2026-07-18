#!/usr/bin/bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
binary_dir="${HOME}/.local/bin"
user_unit_dir=${XDG_CONFIG_HOME:-"${HOME}/.config"}/systemd/user

/usr/bin/install -d -m 0755 -- "$binary_dir" "$user_unit_dir"
/usr/bin/install -m 0755 -- "$project_dir/power-toggle" "$binary_dir/power-toggle"
/usr/bin/install -m 0644 -- \
    "$project_dir/power-toggle.service" "$user_unit_dir/power-toggle.service"

/usr/bin/systemctl --user daemon-reload
/usr/bin/systemctl --user enable power-toggle.service
/usr/bin/systemctl --user restart power-toggle.service

printf 'Installed and started power-toggle.service\n'
printf 'Check it with: systemctl --user status power-toggle.service\n'
