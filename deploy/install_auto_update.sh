#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="lumina-update.service"
TIMER_NAME="lumina-update.timer"
ENV_FILE="$ROOT_DIR/deploy/.env.production"

if [[ -f "$ENV_FILE" ]]; then
	set -a
	# shellcheck disable=SC1090
	source "$ENV_FILE"
	set +a
fi

UPDATE_INTERVAL="${LUMINA_AUTO_UPDATE_INTERVAL:-30min}"

sudo install -m 0755 "$ROOT_DIR/deploy/update_stack.sh" /usr/local/bin/lumina-update

cat <<EOF | sudo tee /etc/systemd/system/$SERVICE_NAME >/dev/null
[Unit]
Description=Lumina stack update job
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$ROOT_DIR
ExecStart=/usr/local/bin/lumina-update
EOF

cat <<EOF | sudo tee /etc/systemd/system/$TIMER_NAME >/dev/null
[Unit]
Description=Run Lumina stack updates periodically

[Timer]
OnBootSec=10min
OnUnitActiveSec=$UPDATE_INTERVAL
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now $TIMER_NAME
sudo systemctl status $TIMER_NAME --no-pager
