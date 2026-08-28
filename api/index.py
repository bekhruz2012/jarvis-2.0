import asyncio
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler


# ============================================================
# IMPORTS
# ============================================================

from ai import ask_jarvis

from security import analyze_message

try:
    from database import increment_stat
except Exception:
    increment_stat = None


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    ""
).strip()

OWNER_ID = os.getenv(
    "OWNER_ID",
    ""
).strip()

try:
    OWNER_ID = int(OWNER_ID)
except Exception:
    OWNER_ID = None


TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
    if BOT_TOKEN
    else ""
)


# ============================================================
# TELEGRAM API
# ============================================================

def telegram_request(
    method,
    data,
):
    """
    Выполняет запрос к Telegram Bot API.
    """

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is not configured"
        )

    url = (
        f"{TELEGRAM_API}/{method}"
    )

    payload = json.dumps(
        data,
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type":
                "application/json",
        },
        method="POST",
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:

            body = (
                response
                .read()
                .decode("utf-8")
            )

            return json.loads(body)

    except urllib.error.HTTPError as e:

        error_body = (
            e.read()
            .decode(
                "utf-8",
                errors="replace",
            )
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


# ============================================================
# SEND MESSAGE
# ============================================================

def send_message(
    chat_id,
    text,
):
    """
    Отправляет сообщение в Telegram.
    """

    if not text:

        return {
            "ok": False,
            "error": "Empty message",
        }

    text = str(text)

    # Telegram limit.
    if len(text) > 4000:

        text = (
            text[:3990]
            + "\n…"
        )

    return telegram_request(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
        },
    )


# ============================================================
# SECURITY NOTIFICATION
# ============================================================

def security_message(
    security_result,
):
    """
    Формирует сообщение Security.
    """

    action = security_result.get(
        "action",
        "allow",
    )

    spam = security_result.get(
        "spam_score",
        0,
    )

    scam = security_result.get(
        "scam_score",
        0,
    )

    reason = security_result.get(
        "reason",
        "",
    )

    if action == "block":

        return (
            "🛡️ SECURITY ALERT\n\n"
            "⛔ Сообщение заблокировано.\n\n"
            f"🛑 Spam: {spam}/100\n"
            f"🎣 Scam: {scam}/100\n\n"
            f"📌 Причина: {reason}"
        )

    if action == "warn":

        return (
            "⚠️ SECURITY WARNING\n\n"
            f"🛑 Spam: {spam}/100\n"
            f"🎣 Scam: {scam}/100\n\n"
            f"📌 Причина: {reason}"
        )

    return None


# ============================================================
# SECURITY STATISTICS
# ============================================================

async def security_stat(
    name,
):
    """
    Безопасно увеличивает Security statistic.
    """

    if increment_stat is None:
        return

    try:

        await increment_stat(
            name
        )

    except Exception as e:

        print(
            "⚠️ Statistic error: "
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# AI
# ============================================================

async def generate_ai_answer(
    user_id,
    text,
):
    """
    Вызывает существующий JARVIS AI.
    """

    try:

        answer = await ask_jarvis(
            user_id=user_id,
            text=text,
        )

        if not answer:

            return (
                "Извините, я не смог "
                "сформировать ответ."
            )

        return str(answer)

    except Exception as e:

        print()
        print(
            "🔥 AI ERROR"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        return (
            "Извините, сейчас произошла "
            "ошибка AI. Попробуйте ещё раз."
        )


# ============================================================
# RUN ASYNC
# ============================================================

def run_async(
    coroutine,
):
    """
    Запускает async функцию
    из serverless handler.
    """

    try:

        return asyncio.run(
            coroutine
        )

    except RuntimeError:

        loop = asyncio.new_event_loop()

        try:

            asyncio.set_event_loop(
                loop
            )

            return loop.run_until_complete(
                coroutine
            )

        finally:

            loop.close()


# ============================================================
# UPDATE PARSING
# ============================================================

def extract_message(
    update,
):
    """
    Извлекает данные Telegram message.
    """

    message = update.get(
        "message"
    )

    if not message:

        return None

    chat = (
        message.get("chat")
        or {}
    )

    user = (
        message.get("from")
        or {}
    )

    chat_id = chat.get(
        "id"
    )

    user_id = user.get(
        "id"
    )

    if user_id is None:

        user_id = chat_id

    text = (
        message.get("text")
        or ""
    ).strip()

    return {
        "message": message,
        "chat_id": chat_id,
        "user_id": user_id,
        "text": text,
    }


# ============================================================
# START
# ============================================================

def process_start(
    chat_id,
):
    """
    Обрабатывает /start.
    """

    reply = (
        "🤖 JARVIS 2.0 ONLINE\n\n"
        "🟢 Telegram: ONLINE\n"
        "🟢 Vercel: ONLINE\n"
        "🟢 AI: ONLINE\n"
        "🟢 Security: ONLINE\n"
        "🟢 Webhook: ONLINE\n\n"
        "Готов к работе."
    )

    return send_message(
        chat_id,
        reply,
    )


# ============================================================
# SECURITY
# ============================================================

def process_security(
    user_id,
    chat_id,
    text,
):
    """
    Передаёт сообщение в Security.
    """

    try:

        result = run_async(
            analyze_message(
                user_id=user_id,
                chat_id=chat_id,
                text=text,
            )
        )

        if not isinstance(
            result,
            dict,
        ):

            print(
                "⚠️ Security returned "
                "invalid result."
            )

            return {
                "action": "allow",
                "spam_score": 0,
                "scam_score": 0,
                "reason": (
                    "Invalid Security result"
                ),
                "event_type": "error",
                "duplicate": False,
            }

        return result

    except Exception as e:

        print()
        print(
            "🔥 SECURITY ERROR"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        # В случае ошибки Security
        # не ломаем весь JARVIS.
        return {
            "action": "allow",
            "spam_score": 0,
            "scam_score": 0,
            "reason": (
                "Security analysis error"
            ),
            "event_type": "error",
            "duplicate": False,
        }


# ============================================================
# MAIN UPDATE PROCESSOR
# ============================================================

def process_update(
    update,
):
    """
    Главный pipeline:

        Telegram
            ↓
        Security
            ↓
        Monitor statistics
            ↓
        AI
            ↓
        Telegram
    """

    data = extract_message(
        update
    )

    if not data:

        return {
            "status": "ignored",
            "reason": "no_message",
        }

    chat_id = data[
        "chat_id"
    ]

    user_id = data[
        "user_id"
    ]

    text = data[
        "text"
    ]

    # ========================================================
    # BASIC VALIDATION
    # ========================================================

    if chat_id is None:

        return {
            "status": "ignored",
            "reason": "no_chat_id",
        }

    if user_id is None:

        user_id = chat_id

    if not text:

        return {
            "status": "ignored",
            "reason": "no_text",
        }

    print()
    print("=" * 60)
    print(
        "📩 TELEGRAM MESSAGE"
    )
    print("=" * 60)

    print(
        f"🆔 Chat ID: {chat_id}"
    )

    print(
        f"👤 User ID: {user_id}"
    )

    print(
        f"💬 Text: {text[:1000]}"
    )

    # ========================================================
    # START
    # ========================================================

    if text.startswith(
        "/start"
    ):

        result = process_start(
            chat_id
        )

        return {
            "status": "ok",
            "action": "start",
            "telegram": result,
        }

    # ========================================================
    # SECURITY
    # ========================================================

    print()
    print(
        "🛡️ Running Security..."
    )

    security = process_security(
        user_id=user_id,
        chat_id=chat_id,
        text=text,
    )

    action = security.get(
        "action",
        "allow",
    )

    spam_score = security.get(
        "spam_score",
        0,
    )

    scam_score = security.get(
        "scam_score",
        0,
    )

    reason = security.get(
        "reason",
        "",
    )

    event_type = security.get(
        "event_type",
        "normal",
    )

    duplicate = security.get(
        "duplicate",
        False,
    )

    print()
    print(
        "🛡️ SECURITY RESULT"
    )

    print(
        f"⚙️ Action: {action}"
    )

    print(
        f"🛑 Spam: {spam_score}/100"
    )

    print(
        f"🎣 Scam: {scam_score}/100"
    )

    print(
        f"📌 Reason: {reason}"
    )

    print(
        f"🔁 Duplicate: {duplicate}"
    )

    # ========================================================
    # BLOCK
    # ========================================================

    if action in {
        "block",
        "blocked",
    }:

        print()
        print(
            "⛔ SECURITY BLOCK"
        )

        # Security уже увеличивает
        # security_blocks внутри
        # analyze_message().

        # Пользователь получает
        # понятное сообщение.
        warning = security_message(
            security
        )

        telegram_result = None

        if warning:

            telegram_result = send_message(
                chat_id,
                warning,
            )

        return {
            "status": "blocked",
            "action": "security_block",
            "security": security,
            "telegram": telegram_result,
        }

    # ========================================================
    # WARNING
    # ========================================================

    if action == "warn":

        print()
        print(
            "⚠️ SECURITY WARNING"
        )

        # Security уже увеличивает
        # security_warnings внутри
        # analyze_message().

        warning = security_message(
            security
        )

        if warning:

            try:

                send_message(
                    chat_id,
                    warning,
                )

            except Exception as e:

                print(
                    "⚠️ Warning send error: "
                    f"{e}"
                )

    # ========================================================
    # AI
    # ========================================================

    print()
    print(
        "🧠 Calling JARVIS AI..."
    )

    try:

        answer = run_async(
            generate_ai_answer(
                user_id=user_id,
                text=text,
            )
        )

    except Exception as e:

        print()
        print(
            "🔥 AI PIPELINE ERROR"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        answer = (
            "Извините, произошла "
            "внутренняя ошибка."
        )

    # ========================================================
    # SEND
    # ========================================================

    telegram_result = send_message(
        chat_id,
        answer,
    )

    print()
    print(
        "📤 JARVIS RESPONSE"
    )

    print(
        answer[:2000]
    )

    # ========================================================
    # RESULT
    # ========================================================

    return {
        "status": "ok",
        "action": "ai_reply",
        "security": {
            "action": action,
            "spam_score": spam_score,
            "scam_score": scam_score,
            "reason": reason,
            "event_type": event_type,
            "duplicate": duplicate,
        },
        "telegram": telegram_result,
    }


# ============================================================
# HTTP HANDLER
# ============================================================

class handler(
    BaseHTTPRequestHandler
):

    # ========================================================
    # JSON RESPONSE
    # ========================================================

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

        self.wfile.write(
            body
        )

    # ========================================================
    # GET
    # ========================================================

    def do_GET(
        self,
    ):

        self.send_json(
            200,
            {
                "status": "online",
                "service": "JARVIS 2.0",
                "telegram": bool(
                    BOT_TOKEN
                ),
                "ai": True,
                "security": True,
                "monitor": True,
                "webhook": "ready",
            },
        )

    # ========================================================
    # POST
    # ========================================================

    def do_POST(
        self,
    ):

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
                        "error": (
                            "Empty request body"
                        ),
                    },
                )

                return

            body = self.rfile.read(
                content_length
            )

            update = json.loads(
                body.decode(
                    "utf-8"
                )
            )

            print()
            print("=" * 60)
            print(
                "📨 JARVIS WEBHOOK"
            )
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