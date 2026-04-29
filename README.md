# tg-notifier

Lightweight Telegram broadcast bot. Any local script can send a message to all
subscribers with one function call.

## Setup

### 1. Create a bot
Talk to [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy the token.

### 2. Clone & install

```bash
git clone <your-repo-url>
cd tg-notifier
sudo bash install.sh
```

The installer will:
- Copy files to `/opt/tg-notifier`
- Create a Python venv and install dependencies
- Register and start a `systemd` service

### 3. Set your token

```bash
sudo nano /opt/tg-notifier/.env
# Set: BOT_TOKEN=your_token_here
sudo systemctl restart tg-notifier
```

### 4. Subscribe

Open Telegram, find your bot, send `/start`.
Anyone on the team can do this — they'll all receive broadcasts.

---

## Usage in any script

Copy `tg_log.py` next to your script (or into a shared utils folder), then:

```python
from sample_usage import log_to_tg

log_to_tg("✅ Cycle complete")
log_to_tg("⚠️ Capital limit exceeded — stopping")
```

To stop the script on a critical alert:

```python
deployed = get_deployed_capital()
if deployed > AVAILABLE_CAPITAL:
    log_to_tg(f"🚨 Capital exceeded: ${deployed:,.0f} > ${AVAILABLE_CAPITAL:,.0f}")
    sys.exit(1)
```

---

## Bot commands

| Command   | Effect                          |
|-----------|---------------------------------|
| `/start`  | Subscribe to broadcasts         |
| `/stop`   | Unsubscribe                     |
| `/status` | Show number of active subscribers |

---

## Service management

```bash
sudo systemctl status tg-notifier
sudo systemctl restart tg-notifier
sudo journalctl -u tg-notifier -f   # live logs
```

## HTTP API

`POST http://127.0.0.1:12345/notify`

```json
{ "message": "your message here" }
```

Only accessible from localhost — not exposed externally.
