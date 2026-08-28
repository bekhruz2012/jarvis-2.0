import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
    if BOT_TOKEN
    else ""
)


# ============================================================
# TELEGRAM
# ============================================================

def telegram_request(method, data):
    """
    Выполняет запрос к Telegram Bot API.
    """

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")

    url = f"{TELEGRAM_API}/{method}"

    payload = json.dumps(data).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=10,
        ) as response:

            body = response.read().decode("utf-8")

            return json.loads(body)

    except urllib.error.HTTPError as e:

        error_body = e.read().decode(
            "utf-8",
            errors="replace",
        )

        print(
            f"❌ Telegram HTTP error: "
            f"{e.code} {error_body}"
        )

        return {
            "ok": False,
            "error": error_body,
        }

    except Exception as e:

        print(
            f"❌ Telegram request error: "
            f"{type(e).__name__}: {e}"
        )

        return {
            "ok": False,
            "error": str(e),
        }


def send_message(chat_id, text):
    """
    Отправляет сообщение пользователю.
    """

    return telegram_request(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
        },
    )


# ============================================================
# TELEGRAM UPDATE
# ============================================================

def process_update(update):
    """
    Обрабатывает Telegram update.
    """

    message = update.get("message")

    if not message:
        return {
            "status": "ignored",
            "reason": "no_message",
        }

    chat = message.get("chat") or {}

    chat_id = chat.get("id")

    if chat_id is None:
        return {
            "status": "ignored",
            "reason": "no_chat_id",
        }

    text = (
        message.get("text")
        or ""
    ).strip()

    if not text:
        return {
            "status": "ignored",
            "reason": "no_text",
        }

    print()
    print("=" * 60)
    print("📩 TELEGRAM MESSAGE")
    print("=" * 60)

    print(
        f"🆔 Chat ID: {chat_id}"
    )

    print(
        f"💬 Text: {text[:1000]}"
    )

    # --------------------------------------------------------
    # /start
    # --------------------------------------------------------

    if text.startswith("/start"):

        reply = (
            "🤖 JARVIS 2.0 ONLINE\n\n"
            "Привет! Я получил твоё сообщение.\n\n"
            "🟢 Telegram: ONLINE\n"
            "🟢 Vercel: ONLINE\n"
            "🟢 Webhook: ONLINE\n\n"
            "🧠 AI-модуль будет подключён следующим этапом."
        )

        result = send_message(
            chat_id,
            reply,
        )

        return {
            "status": "ok",
            "action": "start",
            "telegram": result,
        }

    # --------------------------------------------------------
    # обычное сообщение
    # --------------------------------------------------------

    reply = (
        "🤖 JARVIS получил сообщение:\n\n"
        f"«{text[:3500]}»\n\n"
        "🧠 AI пока находится на этапе подключения."
    )

    result = send_message(
        chat_id,
        reply,
    )

    return {
        "status": "ok",
        "action": "reply",
        "telegram": result,
    }


# ============================================================
# HTTP HANDLER
# ============================================================

class handler(BaseHTTPRequestHandler):

    # --------------------------------------------------------
    # JSON RESPONSE
    # --------------------------------------------------------

    def send_json(
        self,
        status_code,
        data,
    ):

        body = json.dumps(
            data,
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(
            status_code
        )

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.end_headers()

        self.wfile.write(body)

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def do_GET(self):

        self.send_json(
            200,
            {
                "status": "online",
                "service": "JARVIS 2.0",
                "telegram": bool(BOT_TOKEN),
                "webhook": "ready",
            },
        )

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    def do_POST(self):

        try:

            content_length = int(
                self.headers.get(
                    "Content-Length",
                    "0",
                )
            )

            if content_length <= 0:

                self.send_json(
                    400,
                    {
                        "status": "error",
                        "error": "Empty request body",
                    },
                )

                return

            body = self.rfile.read(
                content_length
            )

            update = json.loads(
                body.decode("utf-8")
            )

            print()
            print("=" * 60)
            print("📨 TELEGRAM WEBHOOK")
            print("=" * 60)

            result = process_update(
                update
            )

            self.send_json(
                200,
                result,
            )

        except json.JSONDecodeError:

            self.send_json(
                400,
                {
                    "status": "error",
                    "error": "Invalid JSON",
                },
            )

        except Exception as e:

            print()
            print(
                "🔥 WEBHOOK ERROR"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            self.send_json(
                500,
                {
                    "status": "error",
                    "error": str(e),
                },
            )
