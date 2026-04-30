#!/usr/bin/env bash
# Usage: sudo bash install.sh
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="/etc/systemd/system/tg-notifier.service"

# ── 1. .env ───────────────────────────────────────────────────────────────────
if [ ! -f "$DIR/.env" ]; then
    cp "$DIR/.env.example" "$DIR/.env"
    echo "⚠️  Set your BOT_TOKEN in $DIR/.env, then run: sudo systemctl restart tg-notifier"
fi

# ── 2. venv + deps ────────────────────────────────────────────────────────────
apt-get install -y python3-venv python3-pip > /dev/null
rm -rf "$DIR/.venv"
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install --quiet -r "$DIR/requirements.txt"
# ── 3. systemd service ───────────────────────────────────────────────────────
# ─
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Telegram Notifier Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python bot.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tg-notifier
systemctl restart tg-notifier

# ── 4. install tg_log system-wide ────────────────────────────────────────────
pip install -e "$DIR" --break-system-packages

echo "✅ Done. Logs: sudo journalctl -u tg-notifier -f"