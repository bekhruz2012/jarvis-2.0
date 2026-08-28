import json
import os
from http.server import BaseHTTPRequestHandler


BOT_TOKEN = os.getenv("BOT_TOKEN", "")


def telegram_api(method, data):
    """
    Пока только заготовка.
    На следующем этапе подключим отправку сообщений
    через Telegram Bot API.
    """
    return {
        "ok": True,
        "method": method,
        "data": data,
    }


class handler(BaseHTTPRequestHandler):

    def send_json(self, status_code, data):
        body = json.dumps(
            data,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status_code)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):
        self.send_json(
            200,
            {
                "status": "online",
                "service": "JARVIS 2.0",
                "telegram": bool(BOT_TOKEN),
            }
        )

    def do_POST(self):
        try:
            content_length = int(
                self.headers.get(
                    "Content-Length",
                    0
                )
            )

            body = self.rfile.read(
                content_length
            )

            update = json.loads(
                body.decode("utf-8")
            )

            message = update.get(
                "message",
                {}
            )

            text = message.get(
                "text",
                ""
            )

            chat = message.get(
                "chat",
                {}
            )

            user = message.get(
                "from",
                {}
            )

            result = {
                "status": "received",
                "service": "JARVIS 2.0",
                "message": text,
                "chat_id": chat.get("id"),
                "user_id": user.get("id"),
            }

            print(
                "📩 Telegram update:"
            )

            print(
                json.dumps(
                    result,
                    ensure_ascii=False
                )
            )

            self.send_json(
                200,
                result
            )

        except Exception as e:

            print(
                f"❌ Webhook error: "
                f"{type(e).__name__}: {e}"
            )

            self.send_json(
                500,
                {
                    "status": "error",
                    "error": str(e)
                }
            )