import asyncio
import logging
import os
import time
from collections import deque
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import Conflict, TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)


# ============================================================
# CONFIG
# ============================================================

try:
    from config import (
        TELEGRAM_BOT_TOKEN,
        OWNER_ID,
        SECURITY_ENABLED,
    )
except ImportError:

    TELEGRAM_BOT_TOKEN = os.getenv(
        "TELEGRAM_BOT_TOKEN",
        os.getenv("BOT_TOKEN", ""),
    )

    OWNER_ID = int(
        os.getenv("OWNER_ID", "0")
    )

    SECURITY_ENABLED = (
        os.getenv(
            "SECURITY_ENABLED",
            "true",
        ).lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
    or TELEGRAM_BOT_TOKEN
)

try:
    OWNER_ID = int(
        os.getenv("OWNER_ID") or OWNER_ID
    )
except Exception:
    OWNER_ID = 0


# ============================================================
# OPTIONAL IMPORTS
# ============================================================

try:
    from security import (
        is_security_enabled,
        set_security_enabled,
    )
except Exception:

    def is_security_enabled():
        return bool(SECURITY_ENABLED)

    def set_security_enabled(value):
        return None


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger("JARVIS_MONITOR")


# ============================================================
# GLOBAL STATE
# ============================================================

MONITORING_ENABLED = True

AUTOREPLY_MODE = "auto"
AUTOREPLY_DELAY = 0

START_TIME = time.time()

LAST_HEARTBEAT = time.time()

LAST_TELEGRAM_EVENT = None

LAST_ERROR = None

LAST_SECURITY_EVENT = None

LAST_AUTOREPLY_EVENT = None

LAST_AI_EVENT = None

LAST_DATABASE_EVENT = None


STATS = {
    "messages": 0,
    "scheduled": 0,
    "replies": 0,
    "cancelled": 0,
    "errors": 0,
    "security_blocks": 0,
    "security_allows": 0,
    "ai_requests": 0,
    "ai_errors": 0,
    "database_errors": 0,
    "reconnects": 0,
}


EVENT_LOG = deque(maxlen=200)


# ============================================================
# EXTERNAL CALLBACKS
# ============================================================

_SECURITY_GETTER = None
_SECURITY_SETTER = None


def register_security_callbacks(
    getter=None,
    setter=None,
):
    global _SECURITY_GETTER
    global _SECURITY_SETTER

    _SECURITY_GETTER = getter
    _SECURITY_SETTER = setter


# ============================================================
# EVENT API
# ============================================================

def record_event(
    event_type,
    message,
    level="INFO",
):
    global LAST_ERROR
    global LAST_SECURITY_EVENT
    global LAST_AUTOREPLY_EVENT
    global LAST_AI_EVENT
    global LAST_DATABASE_EVENT
    global LAST_TELEGRAM_EVENT

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    item = {
        "time": now,
        "type": event_type,
        "level": level,
        "message": str(message),
    }

    EVENT_LOG.append(item)

    if event_type == "error":
        LAST_ERROR = item

    elif event_type == "security":
        LAST_SECURITY_EVENT = item

    elif event_type == "autoreply":
        LAST_AUTOREPLY_EVENT = item

    elif event_type == "ai":
        LAST_AI_EVENT = item

    elif event_type == "database":
        LAST_DATABASE_EVENT = item

    elif event_type == "telegram":
        LAST_TELEGRAM_EVENT = item


def monitor_event(
    event_type,
    message,
    level="INFO",
):
    record_event(
        event_type,
        message,
        level,
    )

    logger.info(
        "[%s] %s",
        event_type.upper(),
        message,
    )


def monitor_error(message):
    STATS["errors"] += 1

    record_event(
        "error",
        message,
        "ERROR",
    )

    logger.error(
        "%s",
        message,
    )


def monitor_security(
    message,
    blocked=False,
):
    if blocked:
        STATS["security_blocks"] += 1
    else:
        STATS["security_allows"] += 1

    record_event(
        "security",
        message,
        "WARNING" if blocked else "INFO",
    )


def monitor_autoreply(message):
    record_event(
        "autoreply",
        message,
        "INFO",
    )


def monitor_ai(
    message,
    error=False,
):
    if error:
        STATS["ai_errors"] += 1
    else:
        STATS["ai_requests"] += 1

    record_event(
        "ai",
        message,
        "ERROR" if error else "INFO",
    )


def monitor_database(
    message,
    error=False,
):
    if error:
        STATS["database_errors"] += 1

    record_event(
        "database",
        message,
        "ERROR" if error else "INFO",
    )


def monitor_telegram(message):
    record_event(
        "telegram",
        message,
        "INFO",
    )


# ============================================================
# HEARTBEAT
# ============================================================

def heartbeat():
    global LAST_HEARTBEAT

    LAST_HEARTBEAT = time.time()


def seconds_since_heartbeat():
    return int(
        time.time() - LAST_HEARTBEAT
    )


# ============================================================
# SECURITY
# ============================================================

def get_security_status():

    try:

        if _SECURITY_GETTER:

            return bool(
                _SECURITY_GETTER()
            )

        return bool(
            is_security_enabled()
        )

    except Exception:

        return bool(
            SECURITY_ENABLED
        )


def set_security_status(value):

    global SECURITY_ENABLED

    SECURITY_ENABLED = bool(value)

    try:

        if _SECURITY_SETTER:

            _SECURITY_SETTER(
                bool(value)
            )

        else:

            set_security_enabled(
                bool(value)
            )

    except Exception as e:

        monitor_error(
            f"Security save error: {e}"
        )


# ============================================================
# OWNER CHECK
# ============================================================

async def owner_only(update):

    user = update.effective_user

    if not user:
        return False

    if not OWNER_ID:

        logger.error(
            "OWNER_ID is not configured."
        )

        return False

    if user.id != OWNER_ID:

        try:

            if update.callback_query:

                await update.callback_query.answer(
                    "⛔ Доступ запрещён.",
                    show_alert=True,
                )

            elif update.message:

                await update.message.reply_text(
                    "⛔ Доступ запрещён."
                )

        except Exception:
            pass

        return False

    return True


# ============================================================
# UPTIME
# ============================================================

def uptime_text():

    seconds = int(
        time.time() - START_TIME
    )

    days = seconds // 86400
    seconds %= 86400

    hours = seconds // 3600
    seconds %= 3600

    minutes = seconds // 60
    seconds %= 60

    return (
        f"{days}д "
        f"{hours}ч "
        f"{minutes}м "
        f"{seconds}с"
    )


# ============================================================
# MAIN KEYBOARD
# ============================================================

def main_keyboard():

    security_text = (
        "🛡 Security: ON"
        if get_security_status()
        else "🛡 Security: OFF"
    )

    monitoring_text = (
        "👁 Monitoring: ON"
        if MONITORING_ENABLED
        else "👁 Monitoring: OFF"
    )

    return InlineKeyboardMarkup(
        [

            [
                InlineKeyboardButton(
                    security_text,
                    callback_data="toggle_security",
                )
            ],

            [
                InlineKeyboardButton(
                    monitoring_text,
                    callback_data="toggle_monitoring",
                )
            ],

            [
                InlineKeyboardButton(
                    "🤖 AutoReply",
                    callback_data="autoreply",
                )
            ],

            [
                InlineKeyboardButton(
                    "📊 Status",
                    callback_data="status",
                )
            ],

            [
                InlineKeyboardButton(
                    "📡 Monitor",
                    callback_data="monitor_status",
                )
            ],

        ]
    )


# ============================================================
# AUTOREPLY KEYBOARD
# ============================================================

def autoreply_keyboard():

    return InlineKeyboardMarkup(
        [

            [
                InlineKeyboardButton(
                    "▶️ AUTO",
                    callback_data="ar_auto",
                ),

                InlineKeyboardButton(
                    "⏸ OFF",
                    callback_data="ar_off",
                ),
            ],

            [
                InlineKeyboardButton(
                    "⏱ 0 мин",
                    callback_data="ar_delay_0",
                ),

                InlineKeyboardButton(
                    "⏱ 5 мин",
                    callback_data="ar_delay_5",
                ),
            ],

            [
                InlineKeyboardButton(
                    "⏱ 15 мин",
                    callback_data="ar_delay_15",
                ),

                InlineKeyboardButton(
                    "⏱ 30 мин",
                    callback_data="ar_delay_30",
                ),
            ],

            [
                InlineKeyboardButton(
                    "⏹ Cancel",
                    callback_data="ar_cancel",
                )
            ],

            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="back",
                )
            ],

        ]
    )


# ============================================================
# STATUS
# ============================================================

def status_text():

    security = (
        "🟢 ON"
        if get_security_status()
        else "🔴 OFF"
    )

    monitoring = (
        "🟢 ON"
        if MONITORING_ENABLED
        else "🔴 OFF"
    )

    heartbeat_age = seconds_since_heartbeat()

    heartbeat_status = (
        "🟢 HEALTHY"
        if heartbeat_age < 180
        else "🟡 STALE"
        if heartbeat_age < 600
        else "🔴 DEAD"
    )

    return (
        "🤖 <b>JARVIS 2.0</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n"

        f"🤖 AutoReply: "
        f"<b>{AUTOREPLY_MODE.upper()}</b>\n"

        f"⏱ Delay: "
        f"<b>{AUTOREPLY_DELAY} мин.</b>\n"

        f"🛡 Security: "
        f"<b>{security}</b>\n"

        f"👁 Monitoring: "
        f"<b>{monitoring}</b>\n"

        f"💓 Heartbeat: "
        f"<b>{heartbeat_status}</b>\n"

        f"⏱ Uptime: "
        f"<b>{uptime_text()}</b>\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        f"📩 Messages: "
        f"<b>{STATS['messages']}</b>\n"

        f"⏳ Scheduled: "
        f"<b>{STATS['scheduled']}</b>\n"

        f"💬 Replies: "
        f"<b>{STATS['replies']}</b>\n"

        f"⏹ Cancelled: "
        f"<b>{STATS['cancelled']}</b>\n"

        f"❌ Errors: "
        f"<b>{STATS['errors']}</b>\n\n"

        f"🛡 Security blocks: "
        f"<b>{STATS['security_blocks']}</b>\n"

        f"🧠 AI requests: "
        f"<b>{STATS['ai_requests']}</b>\n"

        f"🧠 AI errors: "
        f"<b>{STATS['ai_errors']}</b>\n"

        f"💾 DB errors: "
        f"<b>{STATS['database_errors']}</b>\n"

        f"🔄 Reconnects: "
        f"<b>{STATS['reconnects']}</b>"
    )


# ============================================================
# MONITOR STATUS
# ============================================================

def monitor_status_text():

    last_event = (
        EVENT_LOG[-1]
        if EVENT_LOG
        else None
    )

    if last_event:

        last_event_text = (
            f"{last_event['time']}\n"
            f"{last_event['type']}: "
            f"{last_event['message']}"
        )

    else:

        last_event_text = (
            "Нет событий."
        )

    return (
        "📡 <b>JARVIS MONITOR</b>\n\n"

        f"💓 Heartbeat: "
        f"<b>{seconds_since_heartbeat()} сек. назад</b>\n"

        f"⏱ Uptime: "
        f"<b>{uptime_text()}</b>\n"

        f"📊 Events: "
        f"<b>{len(EVENT_LOG)}</b>\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        f"📩 Messages: "
        f"<b>{STATS['messages']}</b>\n"

        f"🛡 Blocks: "
        f"<b>{STATS['security_blocks']}</b>\n"

        f"❌ Errors: "
        f"<b>{STATS['errors']}</b>\n"

        f"🧠 AI errors: "
        f"<b>{STATS['ai_errors']}</b>\n"

        f"💾 DB errors: "
        f"<b>{STATS['database_errors']}</b>\n"

        f"🔄 Reconnects: "
        f"<b>{STATS['reconnects']}</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "📝 <b>Последнее событие:</b>\n"
        f"{last_event_text}"
    )


# ============================================================
# LOGS TEXT
# ============================================================

def logs_text(limit=15):

    events = list(EVENT_LOG)[-limit:]

    if not events:

        return (
            "📋 <b>JARVIS LOGS</b>\n\n"
            "Лог пуст."
        )

    lines = [
        "📋 <b>JARVIS LOGS</b>",
        "",
    ]

    for event in reversed(events):

        icon = {
            "ERROR": "🔴",
            "WARNING": "🟡",
            "INFO": "🟢",
        }.get(
            event["level"],
            "⚪",
        )

        lines.append(
            f"{icon} "
            f"<code>{event['time']}</code> "
            f"<b>{event['type']}</b>\n"
            f"{event['message']}"
        )

    return "\n".join(lines)


# ============================================================
# /START
# ============================================================

async def cmd_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    await update.message.reply_text(
        status_text(),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# ============================================================
# /STATUS
# ============================================================

async def cmd_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    await update.message.reply_text(
        status_text(),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# ============================================================
# /STATS
# ============================================================

async def cmd_stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    await update.message.reply_text(
        status_text(),
        parse_mode="HTML",
    )


# ============================================================
# /LOGS
# ============================================================

async def cmd_logs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    await update.message.reply_text(
        logs_text(),
        parse_mode="HTML",
    )


# ============================================================
# /MONITOR_STATUS
# ============================================================

async def cmd_monitor_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    await update.message.reply_text(
        monitor_status_text(),
        parse_mode="HTML",
    )


# ============================================================
# /SECURITY
# ============================================================

async def cmd_security(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    if context.args:

        value = (
            context.args[0]
            .strip()
            .lower()
        )

        if value in {
            "on",
            "1",
            "true",
            "enable",
        }:

            set_security_status(True)

        elif value in {
            "off",
            "0",
            "false",
            "disable",
        }:

            set_security_status(False)

    await update.message.reply_text(
        status_text(),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# ============================================================
# /MONITOR
# ============================================================

async def cmd_monitor(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    global MONITORING_ENABLED

    if not await owner_only(update):
        return

    if context.args:

        value = (
            context.args[0]
            .strip()
            .lower()
        )

        if value in {
            "on",
            "1",
            "true",
            "enable",
        }:

            MONITORING_ENABLED = True

        elif value in {
            "off",
            "0",
            "false",
            "disable",
        }:

            MONITORING_ENABLED = False

    await update.message.reply_text(
        status_text(),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# ============================================================
# /AUTOREPLY
# ============================================================

async def cmd_autoreply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    global AUTOREPLY_MODE
    global AUTOREPLY_DELAY

    if not await owner_only(update):
        return

    if context.args:

        value = (
            context.args[0]
            .strip()
            .lower()
        )

        if value in {
            "on",
            "auto",
            "enable",
        }:

            AUTOREPLY_MODE = "auto"

        elif value in {
            "off",
            "disable",
        }:

            AUTOREPLY_MODE = "off"

        else:

            try:

                delay = int(value)

                if delay >= 0:

                    AUTOREPLY_DELAY = delay
                    AUTOREPLY_MODE = "auto"

            except ValueError:

                pass

    monitor_autoreply(
        f"AutoReply: "
        f"{AUTOREPLY_MODE}, "
        f"delay={AUTOREPLY_DELAY}m"
    )

    await update.message.reply_text(
        (
            "🤖 <b>AUTOREPLY SETTINGS</b>\n\n"
            f"Mode: <b>{AUTOREPLY_MODE}</b>\n"
            f"Delay: <b>{AUTOREPLY_DELAY} min.</b>"
        ),
        parse_mode="HTML",
        reply_markup=autoreply_keyboard(),
    )


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    global MONITORING_ENABLED
    global AUTOREPLY_MODE
    global AUTOREPLY_DELAY

    query = update.callback_query

    if not query:
        return

    if not await owner_only(update):
        return

    await query.answer()

    action = query.data

    # SECURITY

    if action == "toggle_security":

        set_security_status(
            not get_security_status()
        )

        await query.edit_message_text(
            status_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

        return

    # MONITORING

    if action == "toggle_monitoring":

        MONITORING_ENABLED = (
            not MONITORING_ENABLED
        )

        await query.edit_message_text(
            status_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

        return

    # STATUS

    if action == "status":

        await query.edit_message_text(
            status_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

        return

    # MONITOR STATUS

    if action == "monitor_status":

        await query.edit_message_text(
            monitor_status_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

        return

    # AUTOREPLY MENU

    if action == "autoreply":

        await query.edit_message_text(
            (
                "🤖 <b>AUTOREPLY SETTINGS</b>\n\n"
                f"Mode: <b>{AUTOREPLY_MODE}</b>\n"
                f"Delay: <b>{AUTOREPLY_DELAY} min.</b>"
            ),
            parse_mode="HTML",
            reply_markup=autoreply_keyboard(),
        )

        return

    # AUTO

    if action == "ar_auto":

        AUTOREPLY_MODE = "auto"

        monitor_autoreply(
            "AutoReply enabled"
        )

        await query.edit_message_text(
            (
                "🤖 <b>AUTOREPLY ENABLED</b>\n\n"
                f"Delay: "
                f"<b>{AUTOREPLY_DELAY} мин.</b>"
            ),
            parse_mode="HTML",
            reply_markup=autoreply_keyboard(),
        )

        return

    # OFF

    if action == "ar_off":

        AUTOREPLY_MODE = "off"

        monitor_autoreply(
            "AutoReply disabled"
        )

        await query.edit_message_text(
            "⏸️ <b>AUTOREPLY OFF</b>",
            parse_mode="HTML",
            reply_markup=autoreply_keyboard(),
        )

        return

    # DELAYS

    delays = {
        "ar_delay_0": 0,
        "ar_delay_5": 5,
        "ar_delay_15": 15,
        "ar_delay_30": 30,
    }

    if action in delays:

        AUTOREPLY_DELAY = delays[action]

        AUTOREPLY_MODE = "auto"

        monitor_autoreply(
            f"Delay changed to "
            f"{AUTOREPLY_DELAY}m"
        )

        await query.edit_message_text(
            (
                "⏱ <b>AUTOREPLY DELAY</b>\n\n"
                f"Новое время: "
                f"<b>{AUTOREPLY_DELAY} мин.</b>"
            ),
            parse_mode="HTML",
            reply_markup=autoreply_keyboard(),
        )

        return

    # CANCEL

    if action == "ar_cancel":

        STATS["cancelled"] += 1

        monitor_autoreply(
            "Active autoreplies cancelled"
        )

        await query.edit_message_text(
            "⏹ <b>АКТИВНЫЕ ОТВЕТЫ ОТМЕНЕНЫ</b>",
            parse_mode="HTML",
            reply_markup=autoreply_keyboard(),
        )

        return

    # BACK

    if action == "back":

        await query.edit_message_text(
            status_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

        return


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context: ContextTypes.DEFAULT_TYPE,
):

    error = context.error

    if isinstance(error, Conflict):

        monitor_error(
            "TELEGRAM BOT CONFLICT: "
            "another getUpdates instance "
            "is using this Bot Token."
        )

        logger.error(
            "❌ Another Monitor Bot instance "
            "is already polling this token."
        )

        return

    monitor_error(
        f"Telegram error: "
        f"{type(error).__name__}: {error}"
    )


# ============================================================
# MONITOR LOOP
# ============================================================

async def monitor_loop():

    logger.info(
        "📡 JARVIS monitor loop started."
    )

    while True:

        try:

            heartbeat()

            if not MONITORING_ENABLED:

                await asyncio.sleep(60)

                continue

            # --------------------------------------------
            # HEARTBEAT CHECK
            # --------------------------------------------

            if seconds_since_heartbeat() > 600:

                monitor_error(
                    "JARVIS heartbeat is stale."
                )

            await asyncio.sleep(60)

        except asyncio.CancelledError:

            logger.info(
                "📡 Monitor loop stopped."
            )

            raise

        except Exception as e:

            monitor_error(
                f"Monitor loop error: {e}"
            )

            await asyncio.sleep(10)


# ============================================================
# BUILD APPLICATION
# ============================================================

def build_application():

    if not BOT_TOKEN:

        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN / BOT_TOKEN "
            "не найден в Environment."
        )

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            cmd_start,
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            cmd_status,
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            cmd_stats,
        )
    )

    application.add_handler(
        CommandHandler(
            "logs",
            cmd_logs,
        )
    )

    application.add_handler(
        CommandHandler(
            "monitor",
            cmd_monitor,
        )
    )

    application.add_handler(
        CommandHandler(
            "monitor_status",
            cmd_monitor_status,
        )
    )

    application.add_handler(
        CommandHandler(
            "security",
            cmd_security,
        )
    )

    application.add_handler(
        CommandHandler(
            "autoreply",
            cmd_autoreply,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    application.add_error_handler(
        error_handler
    )

    return application


# ============================================================
# START MONITOR BOT
# ============================================================

async def start_monitor_bot():

    logger.info(
        "🤖 Monitor Bot starting..."
    )

    application = build_application()

    try:

        await application.initialize()

        await application.start()

        if not application.updater:

            raise RuntimeError(
                "Telegram updater unavailable."
            )

        try:

            await application.updater.start_polling(
                drop_pending_updates=False
            )

        except Conflict:

            monitor_error(
                "Monitor Bot getUpdates conflict."
            )

            try:
                await application.stop()
            except Exception:
                pass

            try:
                await application.shutdown()
            except Exception:
                pass

            return False

        logger.info(
            "============================================================"
        )

        logger.info(
            "📡 MONITOR BOT ONLINE"
        )

        logger.info(
            "🤖 Monitor Bot подключён."
        )

        logger.info(
            "🛡 Security: %s",
            (
                "ON"
                if get_security_status()
                else "OFF"
            ),
        )

        logger.info(
            "📡 Monitoring: %s",
            (
                "ON"
                if MONITORING_ENABLED
                else "OFF"
            ),
        )

        logger.info(
            "============================================================"
        )

        return application

    except Conflict:

        monitor_error(
            "Monitor Bot conflict."
        )

        try:
            await application.stop()
        except Exception:
            pass

        try:
            await application.shutdown()
        except Exception:
            pass

        return False

    except Exception as e:

        monitor_error(
            f"Monitor Bot startup error: {e}"
        )

        try:
            await application.stop()
        except Exception:
            pass

        try:
            await application.shutdown()
        except Exception:
            pass

        return False


# ============================================================
# STOP MONITOR BOT
# ============================================================

async def stop_monitor_bot(
    application=None,
):

    logger.info(
        "🛑 Monitor Bot stopping..."
    )

    if application:

        try:

            if application.updater:

                await application.updater.stop()

        except Exception:
            pass

        try:

            await application.stop()

        except Exception:
            pass

        try:

            await application.shutdown()

        except Exception:
            pass

    logger.info(
        "🛑 Monitor Bot stopped."
    )


# ============================================================
# STANDALONE
# ============================================================

async def main():

    application = await start_monitor_bot()

    if not application:

        logger.error(
            "Monitor Bot не запущен."
        )

        return

    monitor_task = asyncio.create_task(
        monitor_loop()
    )

    try:

        while True:

            await asyncio.sleep(3600)

    except asyncio.CancelledError:

        raise

    finally:

        monitor_task.cancel()

        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        await stop_monitor_bot(
            application
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "\n🛑 Monitor Bot остановлен."
        )

    except Exception as e:

        print(
            "\n🔥 FATAL MONITOR BOT ERROR"
        )

        print(
            f"{type(e).__name__}: {e}"
        )
