
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
PUBLIC_URL = os.environ.get("RENDER_EXTERNAL_URL")

API = f"https://api.telegram.org/bot{BOT_TOKEN}/"


def telegram_send(method, data):
    response = requests.post(
        API + method,
        json=data,
        timeout=20
    )
    result = response.json()

    if not result.get("ok"):
        print("Telegram error:", result.get("description"))

    return result.get("ok", False)


def send_welcome(chat_id):
    message = (
        "👋 Welcome!\n\n"
        "Thank you for requesting to join our VIP Channel.\n"
        "Your Join Request has been received successfully.\n"
        "Please wait for approval.\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "👋 സ്വാഗതം!\n\n"
        "ഞങ്ങളുടെ VIP Channel-ൽ Join Request അയച്ചതിന് നന്ദി.\n"
        "നിങ്ങളുടെ Request ലഭിച്ചിട്ടുണ്ട്.\n"
        "Admin Approval ലഭിക്കുന്നതുവരെ കാത്തിരിക്കുക.\n\n"
        "Thank you! ❤️"
    )

    telegram_send("sendMessage", {
        "chat_id": chat_id,
        "text": message
    })

    # Optional image
    image_url = os.environ.get("WELCOME_IMAGE_URL", "").strip()

    if image_url:
        telegram_send("sendPhoto", {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": "Welcome! ❤️ | സ്വാഗതം!"
        })

    # Optional video
    video_url = os.environ.get("WELCOME_VIDEO_URL", "").strip()

    if video_url:
        telegram_send("sendVideo", {
            "chat_id": chat_id,
            "video": video_url,
            "caption": "Welcome to our VIP Channel!"
        })


@app.route("/", methods=["GET"])
def home():
    return "Telegram Auto Message Bot is Running!"


@app.route("/telegram", methods=["POST"])
def telegram_webhook():

    if request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    ) != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 403

    update = request.get_json(silent=True) or {}

    join_request = update.get("chat_join_request")

    if join_request:
        user_chat_id = join_request.get("user_chat_id")

        if user_chat_id:
            send_welcome(user_chat_id)

    return jsonify({"ok": True})


def setup_webhook():
    if not BOT_TOKEN or not WEBHOOK_SECRET or not PUBLIC_URL:
        print("Missing environment variables")
        return

    result = requests.post(
        API + "setWebhook",
        json={
            "url": PUBLIC_URL.rstrip("/") + "/telegram",
            "secret_token": WEBHOOK_SECRET,
            "allowed_updates": ["chat_join_request"]
        },
        timeout=20
    ).json()

    print("Webhook setup:", result)


setup_webhook()
