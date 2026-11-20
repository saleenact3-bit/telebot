import os
import sqlite3
import logging

import requests
from flask import Flask, request, jsonify


app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)


# Environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "").strip()
PUBLIC_URL = os.environ.get("RENDER_EXTERNAL_URL", "").strip()

WELCOME_IMAGE_URL = os.environ.get(
    "WELCOME_IMAGE_URL", ""
).strip()

WELCOME_VIDEO_URL = os.environ.get(
    "WELCOME_VIDEO_URL", ""
).strip()

UPDATE_DB_PATH = os.environ.get(
    "UPDATE_DB_PATH",
    "/tmp/telegram_processed_updates.sqlite3"
)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not WEBHOOK_SECRET:
    raise RuntimeError("WEBHOOK_SECRET is missing")

allowed_secret_chars = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789_-"
)

if (
    not 1 <= len(WEBHOOK_SECRET) <= 256
    or any(
        character not in allowed_secret_chars
        for character in WEBHOOK_SECRET
    )
):
    raise RuntimeError(
        "WEBHOOK_SECRET must contain only "
        "English letters, numbers, underscores or hyphens "
        "and must be 1–256 characters long"
    )

API = f"https://api.telegram.org/bot{BOT_TOKEN}/"


# Duplicate update database
def init_update_database():
    with sqlite3.connect(
        UPDATE_DB_PATH,
        timeout=10
    ) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS processed_updates (
                update_id INTEGER PRIMARY KEY,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def claim_update(update_id):
    with sqlite3.connect(
        UPDATE_DB_PATH,
        timeout=10
    ) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO processed_updates (update_id)
            VALUES (?)
            """,
            (update_id,)
        )

        return cursor.rowcount == 1


# Telegram API helper
def telegram_send(method, data):
    try:
        response = requests.post(
            API + method,
            json=data,
            timeout=(5, 25)
        )
    except requests.RequestException as error:
        # Do not log the request URL: it contains the bot token.
        logger.error(
            "Telegram %s request failed (%s)",
            method,
            type(error).__name__
        )
        return False

    try:
        result = response.json()
    except ValueError:
        logger.error(
            "Telegram %s returned a non-JSON response; HTTP %s",
            method,
            response.status_code
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


def send_text(chat_id, text):
    return telegram_send(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        }
    )


def send_image(chat_id, image_url, caption=""):
    return telegram_send(
        "sendPhoto",
        {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": caption
        }
    )


def send_video(chat_id, video_url, caption=""):
    return telegram_send(
        "sendVideo",
        {
            "chat_id": chat_id,
            "video": video_url,
            "caption": caption
        }
    )


# Edit your welcome message here
def send_welcome(user_chat_id, first_name):
    message = (
        f"👋 <b>Welcome, {first_name}!</b>

Thank you for requesting to join our VIP Channel.

Your join request has been received successfully.

Please wait for approval.

━━━━━━━━━━━━━━"
    )

    text_sent = send_text(user_chat_id, message)

    image_sent = None
    video_sent = None

    if WELCOME_IMAGE_URL:
        image_sent = send_image(
            user_chat_id,
            WELCOME_IMAGE_URL,
            "Welcome to our VIP Channel!"
        )

    if WELCOME_VIDEO_URL:
        video_sent = send_video(
            user_chat_id,
            WELCOME_VIDEO_URL,
            "Please watch this important video."
        )

    logger.info(
        "Welcome results: text=%s image=%s video=%s",
        text_sent,
        image_sent,
        video_sent
    )


@app.route("/", methods=["GET"])
def home():
    return "Telegram Auto Message Bot is Running!", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    received_secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    )

    if received_secret != WEBHOOK_SECRET:
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
        is_new_update = claim_update(update_id)
    except sqlite3.Error:
        logger.exception(
            "Database error checking update_id=%s",
            update_id
        )
        return jsonify({"ok": False}), 503

    if not is_new_update:
        logger.info(
            "Duplicate update skipped: update_id=%s",
            update_id
        )
        return jsonify({"ok": True}), 200

    user = join_request.get("from") or {}
    first_name = user.get("first_name") or "Friend"

    logger.info(
        "Sending welcome: update_id=%s",
        update_id
    )

    try:
        send_welcome(user_chat_id, first_name)
    except Exception:
        logger.exception(
            "Welcome failed: update_id=%s",
            update_id
        )

    return jsonify({"ok": True}), 200


def setup_webhook():
    if not PUBLIC_URL:
        logger.error(
            "Webhook setup skipped: RENDER_EXTERNAL_URL is missing"
        )
        return False

    webhook_url = PUBLIC_URL.rstrip("/") + "/webhook"

    success = telegram_send(
        "setWebhook",
        {
            "url": webhook_url,
            "secret_token": WEBHOOK_SECRET,
            "allowed_updates": ["chat_join_request"],
            "max_connections": 1
        }
    )

    logger.info("Webhook setup: %s", success)
    return success


# Run when Gunicorn imports this module
init_update_database()
setup_webhook()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
