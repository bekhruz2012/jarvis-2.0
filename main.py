import asyncio
import os
import time
from contextlib import suppress

from aiohttp import web

from telethon_client import (
    start_telegram,
    stop_telegram,
)

from monitor_bot import (
    start_monitor_bot,
    stop_monitor_bot,
)

from telethon_client import (
    set_monitor_bot,
)


# ============================================================
# CONFIG
# ============================================================

PORT = int(
    os.getenv(
        "PORT",
        "10000",
    )
)

HOST = "0.0.0.0"

KEEP_ALIVE_INTERVAL = 180

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
MONITOR_STARTED = False


# ============================================================
# LOG
# ============================================================

def log(message):

    print(
        f"[JARVIS] {message}",
        flush=True,
    )


# ============================================================
# HTTP
# ============================================================

async def index(request):

    uptime = int(
        time.time() - START_TIME
    )

    return web.json_response(
        {
            "status": "online",
            "service": APP_NAME,
            "telegram": TELEGRAM_STARTED,
            "monitor_bot": MONITOR_STARTED,
            "uptime_seconds": uptime,
            "timestamp": int(time.time()),
        }
    )


async def health(request):

    uptime = int(
        time.time() - START_TIME
    )

    return web.json_response(
        {
            "status": (
                "healthy"
                if TELEGRAM_STARTED
                else "degraded"
            ),
            "service": APP_NAME,
            "telegram": TELEGRAM_STARTED,
            "monitor_bot": MONITOR_STARTED,
            "uptime_seconds": uptime,
        }
    )


async def ping(request):

    return web.Response(
        text="JARVIS 2.0 ONLINE",
        content_type="text/plain",
    )


# ============================================================
# WEB SERVER
# ============================================================

async def start_web_server():

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
        f"{HOST}:{PORT}"
    )

    log("❤️ Health: /health")
    log("🏠 Home: /")
    log("📡 HTTP server uses PORT only")


async def stop_web_server():

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
                f"telegram={TELEGRAM_STARTED} | "
                f"monitor={MONITOR_STARTED}"
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

    global KEEP_ALIVE_TASK
    global TELEGRAM_STARTED
    global MONITOR_STARTED

    print()
    print("=" * 70)
    print("🤖 JARVIS 2.0")
    print("=" * 70)
    print()

    log("🚀 Запуск JARVIS...")

    # ========================================================
    # ENV
    # ========================================================

    log(
        "🔧 Проверяем Environment Variables..."
    )

    required_variables = [
        "TG_API_ID",
        "TG_API_HASH",
        "TG_SESSION",
        "BOT_TOKEN",
        "OWNER_ID",
    ]

    missing = []

    for variable in required_variables:

        if not os.getenv(variable):

            missing.append(variable)

    if missing:

        log(
            "⚠️ Не найдены ENV переменные: "
            + ", ".join(missing)
        )

    else:

        log(
            "✅ Telegram ENV variables: OK"
        )

    # ========================================================
    # HTTP FIRST
    # ========================================================

    await start_web_server()

    # ========================================================
    # KEEP ALIVE
    # ========================================================

    KEEP_ALIVE_TASK = asyncio.create_task(
        keep_alive_loop()
    )

    # ========================================================
    # TELETHON USER CLIENT
    # ========================================================

    log(
        "📱 Запускаем Telegram User Client..."
    )

    try:

        await start_telegram()

        TELEGRAM_STARTED = True

        log(
            "✅ Telegram User Client: ONLINE"
        )

    except Exception as e:

        TELEGRAM_STARTED = False

        log(
            "❌ Telegram startup error: "
            f"{type(e).__name__}: {e}"
        )

        log(
            "⚠️ Monitor Bot не будет запущен, "
            "пока User Client не работает."
        )

        return

    # ========================================================
    # MONITOR BOT
    # ========================================================

    log(
        "🤖 Запускаем Monitor Bot..."
    )

    try:

        monitor_application = (
            await start_monitor_bot()
        )

        if monitor_application is not None:

            set_monitor_bot(
                monitor_application
            )

            MONITOR_STARTED = True

            log(
                "✅ Monitor Bot: ONLINE"
            )

        else:

            MONITOR_STARTED = False

            log(
                "❌ Monitor Bot не вернул Application."
            )

    except Exception as e:

        MONITOR_STARTED = False

        log(
            "❌ Monitor Bot startup error: "
            f"{type(e).__name__}: {e}"
        )

    # ========================================================
    # READY
    # ========================================================

    print()
    print("=" * 70)
    print("✅ JARVIS 2.0 READY")
    print("=" * 70)
    print()

    log(
        f"🌐 PORT = {PORT}"
    )

    log(
        f"📱 Telegram = "
        f"{'ONLINE' if TELEGRAM_STARTED else 'OFFLINE'}"
    )

    log(
        f"🤖 Monitor Bot = "
        f"{'ONLINE' if MONITOR_STARTED else 'OFFLINE'}"
    )

    log(
        "🤖 AutoReply = ENABLED"
    )

    log(
        "🛡 Security = ENABLED"
    )

    log(
        "📡 Monitoring = ENABLED"
    )

    print()


# ============================================================
# SHUTDOWN
# ============================================================

async def shutdown():

    global KEEP_ALIVE_TASK
    global TELEGRAM_STARTED
    global MONITOR_STARTED

    print()
    print("=" * 70)
    print("🛑 JARVIS SHUTDOWN")
    print("=" * 70)

    # ========================================================
    # KEEP ALIVE
    # ========================================================

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

    # ========================================================
    # MONITOR BOT
    # ========================================================

    if MONITOR_STARTED:

        log(
            "🤖 Останавливаем Monitor Bot..."
        )

        try:

            await stop_monitor_bot()

        except Exception as e:

            log(
                "⚠️ Monitor Bot shutdown error: "
                f"{type(e).__name__}: {e}"
            )

        MONITOR_STARTED = False

    # ========================================================
    # TELEGRAM
    # ========================================================

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

    # ========================================================
    # HTTP
    # ========================================================

    await stop_web_server()

    log(
        "✅ JARVIS полностью остановлен."
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    await startup()

    try:

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
        print("=" * 70)
        print("🔥 FATAL JARVIS ERROR")
        print(
            f"{type(e).__name__}: {e}"
        )
        print("=" * 70)