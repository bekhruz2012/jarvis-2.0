import asyncio
import os
import signal
from datetime import datetime, timezone

from config import (
    validate_config,
    OWNER_ID,
)

from database import (
    init_database,
    close_database,
)

from monitor_bot import (
    start_monitor_bot,
)

from telethon_client import (
    start_telegram,
    stop_telegram,
    set_monitor_bot,
)

from autoreply import (
    cancel_all_autoreplies,
)


# ============================================================
# RENDER HTTP SERVER
# ============================================================

HOST = "0.0.0.0"

try:
    PORT = int(os.getenv("PORT", "10000"))
except (TypeError, ValueError):
    PORT = 10000


http_server = None
shutdown_event = None

START_TIME = datetime.now(timezone.utc)


# ============================================================
# HTTP RESPONSE
# ============================================================

def http_response(
    status_code=200,
    body="OK",
    content_type="text/plain; charset=utf-8",
):
    """
    Создаёт простой HTTP response для Render.
    """

    status_texts = {
        200: "OK",
        404: "Not Found",
        405: "Method Not Allowed",
        500: "Internal Server Error",
    }

    status_text = status_texts.get(
        status_code,
        "OK",
    )

    body_bytes = body.encode(
        "utf-8",
        errors="replace",
    )

    headers = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"Connection: close\r\n"
        f"Cache-Control: no-cache, no-store\r\n"
        f"\r\n"
    )

    return (
        headers.encode("utf-8")
        + body_bytes
    )


# ============================================================
# HTTP CLIENT HANDLER
# ============================================================

async def handle_http_client(
    reader,
    writer,
):
    """
    Обрабатывает HTTP-запросы Render.

    Поддерживает:

        GET /
        GET /health
        GET /status
    """

    try:

        # ----------------------------------------------------
        # READ REQUEST
        # ----------------------------------------------------

        try:

            data = await asyncio.wait_for(
                reader.read(8192),
                timeout=10,
            )

        except asyncio.TimeoutError:

            writer.write(
                http_response(
                    408,
                    "Request Timeout",
                )
            )

            await writer.drain()

            return

        if not data:
            return

        request = data.decode(
            "utf-8",
            errors="ignore",
        )

        first_line = (
            request.split(
                "\r\n",
                1,
            )[0]
            .strip()
        )

        parts = first_line.split()

        if len(parts) < 2:

            writer.write(
                http_response(
                    400,
                    "Bad Request",
                )
            )

            await writer.drain()

            return

        method = parts[0].upper()
        path = parts[1]

        # ----------------------------------------------------
        # ONLY GET / HEAD
        # ----------------------------------------------------

        if method not in {
            "GET",
            "HEAD",
        }:

            response = http_response(
                405,
                "Method Not Allowed",
            )

            writer.write(response)

            await writer.drain()

            return

        # ----------------------------------------------------
        # ROOT
        # ----------------------------------------------------

        if path == "/":

            body = (
                "JARVIS 2.0 ONLINE\n"
                "Status: OK\n"
                "Telegram: running\n"
                "Monitor Bot: running\n"
            )

            response = http_response(
                200,
                body,
            )

        # ----------------------------------------------------
        # HEALTH
        # ----------------------------------------------------

        elif path == "/health":

            body = (
                "{"
                "\"status\":\"ok\","
                "\"service\":\"jarvis-2.0\","
                "\"telegram\":\"running\","
                "\"monitor_bot\":\"running\""
                "}"
            )

            response = http_response(
                200,
                body,
                "application/json; charset=utf-8",
            )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        elif path == "/status":

            uptime = (
                datetime.now(timezone.utc)
                - START_TIME
            )

            body = (
                "{"
                f"\"status\":\"ok\","
                f"\"service\":\"jarvis-2.0\","
                f"\"uptime_seconds\":"
                f"{int(uptime.total_seconds())},"
                f"\"port\":{PORT}"
                "}"
            )

            response = http_response(
                200,
                body,
                "application/json; charset=utf-8",
            )

        # ----------------------------------------------------
        # 404
        # ----------------------------------------------------

        else:

            response = http_response(
                404,
                "Not Found",
            )

        # ----------------------------------------------------
        # HEAD
        # ----------------------------------------------------

        if method == "HEAD":

            response_text = response.split(
                b"\r\n\r\n",
                1,
            )[0] + b"\r\n\r\n"

            writer.write(
                response_text
            )

        else:

            writer.write(
                response
            )

        await writer.drain()

    except (
        ConnectionResetError,
        BrokenPipeError,
        asyncio.IncompleteReadError,
    ):
        pass

    except Exception as e:

        print(
            "⚠️ HTTP handler error: "
            f"{type(e).__name__}: {e}"
        )

        try:

            writer.write(
                http_response(
                    500,
                    "Internal Server Error",
                )
            )

            await writer.drain()

        except Exception:
            pass

    finally:

        try:

            writer.close()

            await writer.wait_closed()

        except Exception:
            pass


# ============================================================
# START HTTP SERVER
# ============================================================

async def start_http_server():
    """
    Запускает HTTP server для Render.
    """

    global http_server

    print()
    print(
        "🌐 Starting Render HTTP server..."
    )

    http_server = await asyncio.start_server(
        handle_http_client,
        HOST,
        PORT,
        reuse_address=True,
    )

    addresses = []

    for sock in http_server.sockets or []:

        try:

            addresses.append(
                str(sock.getsockname())
            )

        except Exception:
            pass

    print(
        f"🌐 HTTP server: ONLINE"
    )

    print(
        f"🌐 Host: {HOST}"
    )

    print(
        f"🌐 Port: {PORT}"
    )

    print(
        f"🌐 Addresses: "
        f"{', '.join(addresses)}"
    )

    print(
        "🌐 Health endpoint: /health"
    )

    return http_server


# ============================================================
# STOP HTTP SERVER
# ============================================================

async def stop_http_server():
    """
    Корректно останавливает HTTP server.
    """

    global http_server

    if http_server is None:
        return

    print(
        "🌐 Stopping HTTP server..."
    )

    try:

        http_server.close()

        await http_server.wait_closed()

    except Exception as e:

        print(
            "⚠️ HTTP shutdown error: "
            f"{type(e).__name__}: {e}"
        )

    finally:

        http_server = None

    print(
        "🌐 HTTP server: OFFLINE"
    )


# ============================================================
# SIGNAL HANDLER
# ============================================================

def install_signal_handlers(
    loop,
    shutdown,
):
    """
    Обрабатывает SIGTERM/SIGINT.

    Render отправляет SIGTERM перед остановкой
    сервиса.
    """

    def request_shutdown():

        print()
        print(
            "🛑 Shutdown signal received."
        )

        if not shutdown.is_set():

            shutdown.set()

    for sig in (
        signal.SIGINT,
        signal.SIGTERM,
    ):

        try:

            loop.add_signal_handler(
                sig,
                request_shutdown,
            )

        except (
            NotImplementedError,
            RuntimeError,
        ):

            # Например, если окружение не позволяет
            # устанавливать signal handler.
            pass


# ============================================================
# MAIN
# ============================================================

async def main():

    global shutdown_event

    print()
    print("=" * 60)
    print("🤖 JARVIS 2.0 STARTING")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # SHUTDOWN EVENT
    # --------------------------------------------------------

    shutdown_event = asyncio.Event()

    loop = asyncio.get_running_loop()

    install_signal_handlers(
        loop,
        shutdown_event,
    )

    monitor_application = None

    # --------------------------------------------------------
    # CONFIG
    # --------------------------------------------------------

    try:

        print(
            "⚙️ Validating configuration..."
        )

        validate_config()

        print(
            "✅ Configuration: OK"
        )

    except Exception as e:

        print()
        print(
            "❌ Configuration error:"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        raise

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    try:

        print(
            "💾 Starting database..."
        )

        await init_database()

        print(
            "💾 Database: ONLINE"
        )

    except Exception as e:

        print()
        print(
            "❌ Database startup error:"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        raise

    try:

        # ====================================================
        # HTTP SERVER
        # ====================================================

        try:

            await start_http_server()

        except Exception as e:

            print()
            print(
                "❌ HTTP server startup failed:"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            raise

        # ====================================================
        # TELEGRAM
        # ====================================================

        print()

        print(
            "📱 Starting Telegram..."
        )

        me = await start_telegram()

        if me is None:

            raise RuntimeError(
                "Telegram account is unavailable."
            )

        print(
            "✅ Telegram Client: ONLINE"
        )

        # ====================================================
        # MONITOR BOT
        # ====================================================

        print()

        print(
            "🤖 Starting Monitor Bot..."
        )

        monitor_application = (
            await start_monitor_bot(
                owner_id=OWNER_ID
            )
        )

        if monitor_application is None:

            raise RuntimeError(
                "Monitor Bot application "
                "was not created."
            )

        set_monitor_bot(
            monitor_application.bot
        )

        print(
            "✅ Monitor Bot: ONLINE"
        )

        # ====================================================
        # ONLINE
        # ====================================================

        print()
        print("=" * 60)
        print("🟢 JARVIS 2.0 ONLINE")
        print("=" * 60)
        print()

        print(
            f"👤 Account: "
            f"{getattr(me, 'first_name', 'Unknown')}"
        )

        print(
            f"🆔 ID: "
            f"{getattr(me, 'id', 'Unknown')}"
        )

        username = getattr(
            me,
            "username",
            None,
        )

        if username:

            print(
                f"📛 Username: @{username}"
            )

        print()

        print(
            "🧠 AI: ONLINE"
        )

        print(
            "🛡️ Anti-Spam: 24/7"
        )

        print(
            "🎣 Anti-Scam: 24/7"
        )

        print(
            "🗑️ Deleted messages: ON"
        )

        print(
            "✏️ Edited messages: ON"
        )

        print(
            "📨 Auto Reply: 30 minutes"
        )

        print(
            "🔥 Agro Mode: maximum 30 minutes"
        )

        print()

        print(
            f"🌐 Render Port: {PORT}"
        )

        print(
            "🌐 Health: /health"
        )

        print()

        print(
            "🚀 JARVIS is ready."
        )

        print(
            "Press Ctrl+C to stop."
        )

        print()

        # ====================================================
        # WAIT
        # ====================================================

        await shutdown_event.wait()

    except asyncio.CancelledError:

        print(
            "🛑 Main task cancelled."
        )

        raise

    except KeyboardInterrupt:

        print(
            "🛑 Keyboard interrupt."
        )

    except Exception as e:

        print()
        print(
            "🔥 JARVIS MAIN ERROR"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        raise

    finally:

        print()
        print("=" * 60)
        print("🛑 STOPPING JARVIS")
        print("=" * 60)
        print()

        # ====================================================
        # AUTOREPLY
        # ====================================================

        try:

            print(
                "🤖 Stopping AutoReply..."
            )

            await cancel_all_autoreplies()

            print(
                "🤖 AutoReply: OFFLINE"
            )

        except Exception as e:

            print(
                "⚠️ AutoReply shutdown error: "
                f"{type(e).__name__}: {e}"
            )

        # ====================================================
        # MONITOR BOT
        # ====================================================

        if monitor_application:

            try:

                print(
                    "🤖 Stopping Monitor Bot..."
                )

                updater = getattr(
                    monitor_application,
                    "updater",
                    None,
                )

                if updater:

                    try:

                        if updater.running:

                            await updater.stop()

                    except Exception as e:

                        print(
                            "⚠️ Monitor updater stop error: "
                            f"{type(e).__name__}: {e}"
                        )

                try:

                    if monitor_application.running:

                        await monitor_application.stop()

                except Exception as e:

                    print(
                        "⚠️ Monitor application stop error: "
                        f"{type(e).__name__}: {e}"
                    )

                try:

                    await monitor_application.shutdown()

                except Exception as e:

                    print(
                        "⚠️ Monitor application shutdown error: "
                        f"{type(e).__name__}: {e}"
                    )

                print(
                    "🤖 Monitor Bot: OFFLINE"
                )

            except Exception as e:

                print(
                    "⚠️ Monitor shutdown error: "
                    f"{type(e).__name__}: {e}"
                )

        # ====================================================
        # TELEGRAM
        # ====================================================

        try:

            print(
                "📱 Stopping Telegram..."
            )

            await stop_telegram()

            print(
                "📱 Telegram: OFFLINE"
            )

        except Exception as e:

            print(
                "⚠️ Telegram shutdown error: "
                f"{type(e).__name__}: {e}"
            )

        # ====================================================
        # HTTP
        # ====================================================

        try:

            await stop_http_server()

        except Exception as e:

            print(
                "⚠️ HTTP shutdown error: "
                f"{type(e).__name__}: {e}"
            )

        # ====================================================
        # DATABASE
        # ====================================================

        try:

            print(
                "💾 Closing database..."
            )

            await close_database()

            print(
                "💾 Database: OFFLINE"
            )

        except Exception as e:

            print(
                "⚠️ Database shutdown error: "
                f"{type(e).__name__}: {e}"
            )

        print()
        print("=" * 60)
        print("🔴 JARVIS 2.0 OFFLINE")
        print("=" * 60)
        print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "🛑 JARVIS stopped."
        )

    except Exception as e:

        print()
        print(
            "❌ Fatal error:"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        raise
