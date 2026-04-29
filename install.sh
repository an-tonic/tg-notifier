#!/usr/bin/env bash
# install.sh — clone, configure, and register tg-notifier as a systemd service
# Usage:  sudo bash install.sh

set -e

INSTALL_DIR="/opt/tg-notifier"
SERVICE_FILE="/etc/systemd/system/tg-notifier.service"

# ── 1. Copy files ─────────────────────────────────────────────────────────────
echo "Installing to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
cp -r ./* "$INSTALL_DIR/"

# ── 2. .env ───────────────────────────────────────────────────────────────────
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo ""
    echo "⚠️  Edit $INSTALL_DIR/.env and set your BOT_TOKEN, then re-run:"
    echo "    sudo systemctl restart tg-notifier"
    echo ""
fi

# ── 3. Python venv + deps ─────────────────────────────────────────────────────
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# ── 4. systemd service ────────────────────────────────────────────────────────
cp "$INSTALL_DIR/tg-notifier.service" "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable tg-notifier
systemctl restart tg-notifier

echo "✅ tg-notifier installed and running."
echo "   Status:  sudo systemctl status tg-notifier"
echo "   Logs:    sudo journalctl -u tg-notifier -f"
