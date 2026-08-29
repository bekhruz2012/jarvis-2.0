import asyncio
import os
import time
from contextlib import suppress

from aiohttp import web

from telethon_client import start_telegram, stop_telegram

# ============================================================
# CONFIG
# ============================================================

PORT = int(os.getenv("PORT", "10000"))

HOST = "0.0.0.0"

KEEP_ALIVE_INTERVAL = 180  # 3 минуты

APP_NAME = "JARVIS 2.0"


# ============================================================
# GLOBAL STATE
# ============================================================

START_TIME = time.time()

WEB_APP = None
WEB_RUNNER = None
WEB_SITE = None

KEEP_ALIVE_TASK = None
TELEGRAM_STARTED = False


# ============================================================
# LOGGING
# ============================================================

def log(message):
    """
    Единый формат логов.
    """

    print(
        f"[JARVIS] {message}",
        flush=True,
    )


# ============================================================
# HTTP ROUTES
# ============================================================

async def index(request):
    """
    Главная страница.
    """

    uptime = int(
        time.time() - START_TIME
    )

    return web.json_response(
        {
            "status": "online",
            "service": APP_NAME,
            "telegram": TELEGRAM_STARTED,
            "uptime_seconds": uptime,
            "timestamp": int(time.time()),
        }
    )


async def health(request):
    """
    Health check для Render.
    """

    uptime = int(
        time.time() - START_TIME
    )

    return web.json_response(
        {
            "status": "healthy",
            "service": APP_NAME,
            "telegram": TELEGRAM_STARTED,
            "uptime_seconds": uptime,
        }
    )


async def ping(request):
    """
    Простой ping endpoint.
    """

    return web.Response(
        text="JARVIS 2.0 ONLINE",
        content_type="text/plain",
    )


# ============================================================
# WEB SERVER
# ============================================================

async def start_web_server():
    """
    Запускает HTTP сервер.

    Render требует, чтобы Web Service
    слушал порт из переменной PORT.
    """

    global WEB_APP
    global WEB_RUNNER
    global WEB_SITE

    log("🌐 Запускаем HTTP server...")

    WEB_APP = web.Application()

    WEB_APP.router.add_get(
        "/",
        index,
    )

    WEB_APP.router.add_get(
        "/health",
        health,
    )

    WEB_APP.router.add_get(
        "/ping",
        ping,
    )

    WEB_RUNNER = web.AppRunner(
        WEB_APP,
        access_log=None,
    )

    await WEB_RUNNER.setup()

    WEB_SITE = web.TCPSite(
        WEB_RUNNER,
        HOST,
        PORT,
    )

    await WEB_SITE.start()

    log(
        f"🌐 HTTP server: ONLINE "
        f"http://{HOST}:{PORT}"
    )

    log(
        f"❤️ Health: /health"
    )

    log(
        f"🏠 Home: /"
    )


async def stop_web_server():
    """
    Останавливает HTTP сервер.
    """

    global WEB_APP
    global WEB_RUNNER
    global WEB_SITE

    log("🌐 Останавливаем HTTP server...")

    if WEB_SITE is not None:

        with suppress(Exception):
            await WEB_SITE.stop()

        WEB_SITE = None

    if WEB_RUNNER is not None:

        with suppress(Exception):
            await WEB_RUNNER.cleanup()

        WEB_RUNNER = None

    WEB_APP = None

    log("🌐 HTTP server: OFFLINE")


# ============================================================
# KEEP ALIVE
# ============================================================

async def keep_alive_loop():
    """
    Внутренний heartbeat.

    Каждые 3 минуты выводит heartbeat в Render Logs.

    ВАЖНО:
    Этот цикл поддерживает активность самого процесса.
    Для Render Web Service также обязательно наличие
    HTTP-сервера на PORT.
    """

    log(
        "💓 Keep-alive loop запущен "
        f"(каждые {KEEP_ALIVE_INTERVAL} сек.)"
    )

    while True:

        try:

            await asyncio.sleep(
                KEEP_ALIVE_INTERVAL
            )

            uptime = int(
                time.time() - START_TIME
            )

            log(
                f"💓 JARVIS heartbeat | "
                f"uptime={uptime}s | "
                f"telegram={TELEGRAM_STARTED}"
            )

        except asyncio.CancelledError:

            log(
                "💓 Keep-alive loop остановлен."
            )

            raise

        except Exception as e:

            log(
                "⚠️ Keep-alive error: "
                f"{type(e).__name__}: {e}"
            )


# ============================================================
# STARTUP
# ============================================================

async def startup():
    """
    Полный запуск JARVIS.
    """

    global KEEP_ALIVE_TASK
    global TELEGRAM_STARTED

    print()
    print("=" * 70)
    print("🤖 JARVIS 2.0")
    print("=" * 70)
    print()

    log("🚀 Запуск JARVIS...")

    # --------------------------------------------------------
    # ENV CHECK
    # --------------------------------------------------------

    log("🔧 Проверяем Environment Variables...")

    required_variables = [
        "TG_API_ID",
        "TG_API_HASH",
        "TG_SESSION",
    ]

    missing = []

    for variable in required_variables:

        value = os.getenv(variable)

        if not value:

            missing.append(variable)

    if missing:

        log(
            "⚠️ Не найдены ENV переменные: "
            + ", ".join(missing)
        )

        log(
            "⚠️ Telegram может не запуститься."
        )

    else:

        log(
            "✅ Telegram ENV variables: OK"
        )

    # --------------------------------------------------------
    # WEB SERVER FIRST
    # --------------------------------------------------------

    # Очень важно для Render:
    # сначала поднимаем HTTP server.
    await start_web_server()

    # --------------------------------------------------------
    # KEEP ALIVE
    # --------------------------------------------------------

    KEEP_ALIVE_TASK = asyncio.create_task(
        keep_alive_loop()
    )

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    log(
        "📱 Запускаем Telegram Client..."
    )

    try:

        await start_telegram()

        TELEGRAM_STARTED = True

        log(
            "✅ Telegram Client: ONLINE"
        )

    except Exception as e:

        TELEGRAM_STARTED = False

        log(
            "❌ Telegram startup error: "
            f"{type(e).__name__}: {e}"
        )

        # ----------------------------------------------------
        # ВАЖНО
        # ----------------------------------------------------
        #
        # Не завершаем HTTP server.
        #
        # Благодаря этому Render получает ответ,
        # а ошибка Telegram видна в Logs.
        #

        log(
            "⚠️ HTTP server продолжает работать."
        )

    # --------------------------------------------------------
    # READY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("✅ JARVIS 2.0 READY")
    print("=" * 70)
    print()

    log(
        f"🌐 PORT = {PORT}"
    )

    log(
        "❤️ Health endpoint = /health"
    )

    log(
        f"💓 Heartbeat = every "
        f"{KEEP_ALIVE_INTERVAL} seconds"
    )

    log(
        f"📱 Telegram = "
        f"{'ONLINE' if TELEGRAM_STARTED else 'OFFLINE'}"
    )

    print()


# ============================================================
# SHUTDOWN
# ============================================================

async def shutdown():
    """
    Корректно останавливает JARVIS.
    """

    global KEEP_ALIVE_TASK
    global TELEGRAM_STARTED

    print()
    print("=" * 70)
    print("🛑 JARVIS SHUTDOWN")
    print("=" * 70)

    # --------------------------------------------------------
    # KEEP ALIVE
    # --------------------------------------------------------

    if KEEP_ALIVE_TASK is not None:

        log(
            "💓 Останавливаем keep-alive..."
        )

        KEEP_ALIVE_TASK.cancel()

        with suppress(
            asyncio.CancelledError
        ):

            await KEEP_ALIVE_TASK

        KEEP_ALIVE_TASK = None

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    if TELEGRAM_STARTED:

        log(
            "📱 Останавливаем Telegram..."
        )

        try:

            await stop_telegram()

        except Exception as e:

            log(
                "⚠️ Telegram shutdown error: "
                f"{type(e).__name__}: {e}"
            )

        TELEGRAM_STARTED = False

    # --------------------------------------------------------
    # WEB
    # --------------------------------------------------------

    await stop_web_server()

    log(
        "✅ JARVIS полностью остановлен."
    )


# ============================================================
# MAIN
# ============================================================

async def main():
    """
    Главная функция.
    """

    await startup()

    try:

        # ----------------------------------------------------
        # НЕ ДАЁМ ПРОЦЕССУ ЗАВЕРШИТЬСЯ
        # ----------------------------------------------------

        while True:

            await asyncio.sleep(
                3600
            )

    except asyncio.CancelledError:

        log(
            "⚠️ Main task cancelled."
        )

        raise

    finally:

        await shutdown()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print()
        print(
            "🛑 JARVIS остановлен вручную."
        )

    except Exception as e:

        print()
        print(
            "=" * 70
        )

        print(
            "🔥 FATAL JARVIS ERROR"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        print(
            "=" * 70
        )