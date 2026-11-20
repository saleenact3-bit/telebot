import os
import sqlite3
import logging

import requests
from flask import Flask, request, jsonify


app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "").strip()
PUBLIC_URL = os.environ.get("RENDER_EXTERNAL_URL", "").strip()

WELCOME_IMAGE_URL = os.environ.get(
    "WELCOME_IMAGE_URL", ""
).strip()

WELCOME_VIDEO_URL = os.environ.get(
    "WELCOME_VIDEO_URL", ""
).strip()

API = f"https://api.telegram.org/bot{BOT_TOKEN}/"

DATABASE_PATH = os.environ.get(
    "UPDATE_DB_PATH",
    "/tmp/telegram_join_requests.sqlite3"
)


# Remember requests that have already been handled.
def prepare_database():
    with sqlite3.connect(DATABASE_PATH, timeout=10) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS handled_requests (
                update_id INTEGER PRIMARY KEY
            )
        """)


def is_new_request(update_id):
    with sqlite3.connect(DATABASE_PATH, timeout=10) as db:
        cursor = db.execute(
            """
            INSERT OR IGNORE INTO handled_requests (update_id)
            VALUES (?)
            """,
            (update_id,)
        )
        return cursor.rowcount == 1


def telegram_send(method, data):
    try:
        response = requests.post(
            API + method,
            json=data,
            timeout=(5, 25)
        )
    except requests.RequestException as error:
        logger.error(
            "Telegram %s request failed: %s",
            method,
            type(error).__name__
        )
        return False

    try:
        result = response.json()
    except ValueError:
        logger.error(
            "Telegram returned an invalid response for %s",
            method
        )
        return False

    if not result.get("ok"):
        logger.error(
            "Telegram %s error: %s",
            method,
            result.get("description", "Unknown error")
        )
        return False

    return True


def send_welcome(chat_id, first_name):
    from html import escape

    safe_first_name = escape(first_name)

    message = (
        f"👋 <b>Welcome, {safe_first_name}!</b>\n\n"
        "Thank you for requesting to join our VIP Channel.\n\n"
        "Your join request has been received successfully.\n\n"
        "Please wait for approval.\n\n"
        "━━━━━━━━━━━━━━"
    )

    telegram_send(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
    )

    if WELCOME_IMAGE_URL:
        telegram_send(
            "sendPhoto",
            {
                "chat_id": chat_id,
                "photo": WELCOME_IMAGE_URL
            }
        )

    if WELCOME_VIDEO_URL:
        telegram_send(
            "sendVideo",
            {
                "chat_id": chat_id,
                "video": WELCOME_VIDEO_URL
            }
        )


@app.route("/", methods=["GET"])
def home():
    return "Telegram Auto Message Bot is Running!", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    received_secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    )

    if not WEBHOOK_SECRET or received_secret != WEBHOOK_SECRET:
        return jsonify({"ok": False}), 403

    update = request.get_json(silent=True)

    if not isinstance(update, dict):
        return jsonify({"ok": True}), 200

    join_request = update.get("chat_join_request")

    if not isinstance(join_request, dict):
        return jsonify({"ok": True}), 200

    update_id = update.get("update_id")
    user_chat_id = join_request.get("user_chat_id")

    if update_id is None or not user_chat_id:
        return jsonify({"ok": True}), 200

    try:
        new_request = is_new_request(update_id)
    except sqlite3.Error:
        logger.exception("Database check failed")
        return jsonify({"ok": False}), 503

    if not new_request:
        logger.info(
            "Duplicate skipped: %s",
            update_id
        )
        return jsonify({"ok": True}), 200

    user = join_request.get("from") or {}
    first_name = user.get("first_name") or "Friend"

    logger.info(
        "Sending welcome: %s",
        update_id
    )

    try:
        send_welcome(user_chat_id, first_name)
    except Exception:
        logger.exception("Welcome sending failed")

    return jsonify({"ok": True}), 200


def setup_webhook():
    if not BOT_TOKEN or not WEBHOOK_SECRET or not PUBLIC_URL:
        logger.error(
            "BOT_TOKEN, WEBHOOK_SECRET or "
            "RENDER_EXTERNAL_URL is missing"
        )
        return

    success = telegram_send(
        "setWebhook",
        {
            "url": PUBLIC_URL.rstrip("/") + "/webhook",
            "secret_token": WEBHOOK_SECRET,
            "allowed_updates": ["chat_join_request"],
            "max_connections": 1
        }
    )

    logger.info("Webhook setup: %s", success)


prepare_database()
setup_webhook()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
