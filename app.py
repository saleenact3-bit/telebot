import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
PUBLIC_URL = os.environ.get("RENDER_EXTERNAL_URL")

WELCOME_IMAGE_URL = os.environ.get("WELCOME_IMAGE_URL", "")
WELCOME_VIDEO_URL = os.environ.get("WELCOME_VIDEO_URL", "")

API = f"https://api.telegram.org/bot{BOT_TOKEN}/"


def telegram_send(method, data):
    try:
        response = requests.post(API + method, json=data, timeout=25)
        result = response.json()

        if not result.get("ok"):
            print("Telegram error:", result.get("description"))

        return result.get("ok", False)
    except Exception as e:
        print("Telegram request failed:", e)
        return False


def send_text(chat_id, text):
    return telegram_send(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
    )


def send_image(chat_id, image_url, caption=""):
    return telegram_send(
        "sendPhoto",
        {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
    )


def send_video(chat_id, video_url, caption=""):
    return telegram_send(
        "sendVideo",
        {
            "chat_id": chat_id,
            "video": video_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
    )


def send_welcome(user_chat_id, first_name):
    text = f"""
👋 <b>Welcome to eraning star team, {first_name}!</b>

Thank you for requesting to join our VIP Channel.

Your join request has been received successfully.

Please wait for approval.

━━━━━━━━━━━━━━

"""

    send_text(user_chat_id, text)

    if WELCOME_IMAGE_URL:
        send_image(
            user_chat_id,
            WELCOME_IMAGE_URL,
            "Welcome to our VIP Channel 🎉"
        )

    if WELCOME_VIDEO_URL:
        send_video(
            user_chat_id,
            WELCOME_VIDEO_URL,
            "Please watch this important video 🎥"
        )


@app.route("/", methods=["GET"])
def home():
    return "Telegram Auto Message Bot is Running!", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")

    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        return jsonify({"ok": False}), 403

    update = request.get_json(silent=True)

    if not update:
        return jsonify({"ok": True}), 200

    join_request = update.get("chat_join_request")

    if join_request:
        user = join_request.get("from", {})
        user_chat_id = join_request.get("user_chat_id")
        first_name = user.get("first_name", "Friend")

        if user_chat_id:
            send_welcome(user_chat_id, first_name)

    return jsonify({"ok": True}), 200


def setup_webhook():
    if not BOT_TOKEN or not PUBLIC_URL:
        print("BOT_TOKEN or RENDER_EXTERNAL_URL missing")
        return

    webhook_url = PUBLIC_URL.rstrip("/") + "/webhook"

    result = telegram_send(
        "setWebhook",
        {
            "url": webhook_url,
            "secret_token": WEBHOOK_SECRET,
            "allowed_updates": ["chat_join_request"],
            "drop_pending_updates": True
        }
    )

    print("Webhook setup:", result)


setup_webhook()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
