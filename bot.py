"""
tg-notifier: Telegram broadcast bot + local HTTP endpoint.

Start:  python bot.py
Config: .env file (BOT_TOKEN, PORT)

Any script can send a message via:
    POST http://localhost:12345/notify
    Body: { "message": "your text" }

All users who have sent /start to the bot receive it.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 12345))
SUBSCRIBERS_FILE = Path(__file__).parent / "subscribers.json"

if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN not set in .env", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ── Subscriber store ──────────────────────────────────────────────────────────

def load_subscribers() -> set[int]:
    if SUBSCRIBERS_FILE.exists():
        return set(json.loads(SUBSCRIBERS_FILE.read_text()))
    return set()


def save_subscribers(subs: set[int]):
    SUBSCRIBERS_FILE.write_text(json.dumps(list(subs)))


subscribers: set[int] = load_subscribers()


# ── Telegram handlers ─────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in subscribers:
        subscribers.add(chat_id)
        save_subscribers(subscribers)
        log.info(f"New subscriber: {chat_id}")
    await update.message.reply_text(
        "✅ Subscribed. You'll receive all broadcast messages sent to this bot."
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.discard(chat_id)
    save_subscribers(subscribers)
    log.info(f"Unsubscribed: {chat_id}")
    await update.message.reply_text("🔕 Unsubscribed. Send /start to resubscribe.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"👥 Active subscribers: {len(subscribers)}")


# ── Broadcast (called from HTTP thread) ──────────────────────────────────────

_app: Application = None  # set after build


def broadcast_sync(message: str):
    """Thread-safe broadcast — called from the HTTP thread."""
    if not subscribers:
        log.warning("No subscribers, message dropped")
        return

    async def _send():
        dead = set()
        for chat_id in list(subscribers):
            try:
                await _app.bot.send_message(chat_id=chat_id, text=message)
            except Exception as e:
                log.warning(f"Failed to send to {chat_id}: {e} — removing")
                dead.add(chat_id)
        if dead:
            subscribers.difference_update(dead)
            save_subscribers(subscribers)

    asyncio.run_coroutine_threadsafe(_send(), _app.update_queue._loop).result(timeout=10)


# ── HTTP server ───────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # suppress default access logs

    def do_POST(self):
        if self.path != "/notify":
            self._respond(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body)
            message = data.get("message", "").strip()
        except json.JSONDecodeError:
            self._respond(400, "Invalid JSON")
            return

        if not message:
            self._respond(400, "Empty message")
            return

        try:
            broadcast_sync(message)
            self._respond(200, "OK")
            log.info(f"Broadcast: {message[:80]}")
        except Exception as e:
            log.error(f"Broadcast failed: {e}")
            self._respond(500, str(e))

    def _respond(self, code: int, text: str):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode())


def run_http_server():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    log.info(f"HTTP server listening on 127.0.0.1:{PORT}")
    server.serve_forever()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global _app

    _app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    _app.add_handler(CommandHandler("start", start))
    _app.add_handler(CommandHandler("stop", stop))
    _app.add_handler(CommandHandler("status", status))

    # HTTP server runs in background thread
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()

    log.info("Bot started. Press Ctrl+C to stop.")
    _app.run_polling(stop_signals=[signal.SIGINT, signal.SIGTERM])


if __name__ == "__main__":
    main()
