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
from telegram.error import Forbidden, ChatMigrated
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
# Structure: { "chat_id": ["topic1", "topic2", ...] }
# "default" topic = receives all messages with no topic specified

DEFAULT_TOPIC = "default"


def load_subscribers() -> dict[str, list[str]]:
    if SUBSCRIBERS_FILE.exists():
        data = json.loads(SUBSCRIBERS_FILE.read_text())
        # migrate old flat list format
        if isinstance(data, list):
            return {str(chat_id): [DEFAULT_TOPIC] for chat_id in data}
        return data
    return {}


def save_subscribers(subs: dict[str, list[str]]):
    SUBSCRIBERS_FILE.write_text(json.dumps(subs, indent=2))


subscribers: dict[str, list[str]] = load_subscribers()


# ── Telegram handlers ─────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id not in subscribers:
        subscribers[chat_id] = [DEFAULT_TOPIC]
        save_subscribers(subscribers)
        log.info(f"New subscriber: {chat_id}")
    await update.message.reply_text(
        "✅ Subscribed to 'default' topic.\n"
        "Use /subscribe <topic> to subscribe to a specific topic.\n"
        "Use /topics to see your subscriptions."
    )


async def stop(update: Update):
    chat_id = str(update.effective_chat.id)
    subscribers.pop(chat_id, None)
    save_subscribers(subscribers)
    log.info(f"Unsubscribed: {chat_id}")
    await update.message.reply_text("🔕 Fully unsubscribed. Send /start to resubscribe.")


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not context.args:
        await update.message.reply_text("Usage: /subscribe <topic>")
        return
    topic = context.args[0].strip()
    if chat_id not in subscribers:
        subscribers[chat_id] = []
    if topic not in subscribers[chat_id]:
        subscribers[chat_id].append(topic)
        save_subscribers(subscribers)
        log.info(f"{chat_id} subscribed to topic: {topic}")
    await update.message.reply_text(f"✅ Subscribed to topic: {topic}")


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not context.args:
        await update.message.reply_text("Usage: /unsubscribe <topic>")
        return
    topic = context.args[0].strip()
    if chat_id in subscribers and topic in subscribers[chat_id]:
        subscribers[chat_id].remove(topic)
        save_subscribers(subscribers)
        log.info(f"{chat_id} unsubscribed from topic: {topic}")
    await update.message.reply_text(f"🔕 Unsubscribed from topic: {topic}")


async def topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    subs = subscribers.get(chat_id, [])
    if subs:
        await update.message.reply_text("📋 Your topics:\n" + "\n".join(f"  • {t}" for t in subs))
    else:
        await update.message.reply_text("You have no topic subscriptions. Send /start to begin.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"👥 Active subscribers: {len(subscribers)}")


# ── Broadcast (called from HTTP thread) ──────────────────────────────────────

_app: Application = None  # set after build


def broadcast_sync(message: str, topic: str = DEFAULT_TOPIC):
    """Send message to all subscribers of the given topic."""
    recipients = [
        int(chat_id)
        for chat_id, topics in subscribers.items()
        if topic in topics
    ]
    if not recipients:
        log.warning(f"No subscribers for topic '{topic}', message dropped")
        return

    async def _send():
        dead = set()
        for chat_id in recipients:
            try:
                await _app.bot.send_message(chat_id=chat_id, text=message)
            except (Forbidden, ChatMigrated) as e:
                log.warning(f"Removing unreachable subscriber {chat_id}: {e}")
                dead.add(str(chat_id))
            except Exception as e:
                log.warning(f"Failed to send to {chat_id}: {e}")
        if dead:
            for chat_id in dead:
                subscribers.pop(chat_id, None)
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
            message = str(data.get("message", "")).strip()

            if not message:
                self._respond(400, "Empty message")
                return
            topic = str(data.get("topic", DEFAULT_TOPIC)).strip() or DEFAULT_TOPIC
        except json.JSONDecodeError:
            self._respond(400, "Invalid JSON")
            return

        try:
            broadcast_sync(message, topic)
            self._respond(200, "OK")
            log.info(f"Broadcast [{topic}]: {message[:80]}")
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
    _app.add_handler(CommandHandler("subscribe", subscribe))
    _app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    _app.add_handler(CommandHandler("topics", topics))
    _app.add_handler(CommandHandler("status", status))

    # HTTP server runs in background thread
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()

    log.info("Bot started. Press Ctrl+C to stop.")
    _app.run_polling(stop_signals=[signal.SIGINT, signal.SIGTERM])


if __name__ == "__main__":
    main()
