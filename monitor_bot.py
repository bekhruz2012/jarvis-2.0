from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    BOT_TOKEN,
    OWNER_ID,
    MONITOR_ENABLED,
)

from ai import (
    get_mode,
    set_normal_mode,
    set_agro_mode,
    get_agro_remaining,
)

from security import (
    set_security_enabled,
    is_security_enabled,
)

from autoreply import (
    get_autoreply_status,
    get_autoreply_settings_runtime,
    get_current_settings,
    set_autoreply_settings_runtime,
    cancel_all_autoreplies,
    approve_pending_reply,
    deny_pending_reply,
    get_pending_reply,
    set_pending_reply_text,
)


# ============================================================
# RUNTIME
# ============================================================

_monitoring_enabled = bool(
    MONITOR_ENABLED
)

_monitor_application = None

_editing_reply_id = None


# ============================================================
# MONITORING
# ============================================================

def set_monitoring_enabled(
    enabled: bool,
):
    global _monitoring_enabled

    _monitoring_enabled = bool(
        enabled
    )

    print(
        f"📡 Monitoring: "
        f"{'ON' if _monitoring_enabled else 'OFF'}"
    )


def is_monitoring_enabled() -> bool:

    return _monitoring_enabled


# ============================================================
# OWNER
# ============================================================

def is_owner(
    update: Update,
) -> bool:

    user = update.effective_user

    if user is None:
        return False

    return user.id == OWNER_ID


async def owner_only(
    update: Update,
) -> bool:

    if is_owner(update):
        return True

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

    except Exception as e:

        print(
            f"⚠️ Owner check error: {e}"
        )

    return False


# ============================================================
# FORMAT TIME
# ============================================================

def format_time(
    seconds: int,
) -> str:

    seconds = max(
        0,
        int(seconds),
    )

    minutes = seconds // 60

    seconds %= 60

    if minutes:

        return (
            f"{minutes} мин. "
            f"{seconds} сек."
        )

    return f"{seconds} сек."


# ============================================================
# JARVIS MODE
# ============================================================

def mode_text() -> str:

    mode = get_mode()

    if mode == "agro":

        remaining = get_agro_remaining()

        return (
            "🔴 AGRO\n"
            f"⏳ Осталось: "
            f"{format_time(remaining)}"
        )

    return "🟢 NORMAL"


# ============================================================
# AUTOREPLY MODE TEXT
# ============================================================

def autoreply_mode_text(
    mode: str,
) -> str:

    if mode == "auto":

        return "🤖 АВТО"

    if mode == "ask":

        return "❓ СПРОСИТЬ РАЗРЕШЕНИЕ"

    return "✋ ВЫКЛЮЧЕНО"


# ============================================================
# AUTOREPLY STATUS TEXT
# ============================================================

def autoreply_status_text() -> str:

    settings = (
        get_autoreply_settings_runtime()
    )

    mode = settings.get(
        "mode",
        "off",
    )

    delay = settings.get(
        "delay_minutes",
        0,
    )

    return (
        f"🤖 Auto Reply: "
        f"<b>{autoreply_mode_text(mode)}</b>\n"
        f"⏱ Задержка: "
        f"<b>{delay} мин.</b>"
    )


# ============================================================
# MAIN KEYBOARD
# ============================================================

def main_keyboard():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🤖 Автоответчик",
                    callback_data="autoreply_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🛡 Security "
                    + (
                        "🟢"
                        if is_security_enabled()
                        else "🔴"
                    ),
                    callback_data="toggle_security",
                ),
                InlineKeyboardButton(
                    "👁 Monitoring "
                    + (
                        "🟢"
                        if is_monitoring_enabled()
                        else "🔴"
                    ),
                    callback_data="toggle_monitoring",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🟢 NORMAL",
                    callback_data="normal",
                ),
                InlineKeyboardButton(
                    "🔴 AGRO",
                    callback_data="agro",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Statistics",
                    callback_data="statistics",
                ),
                InlineKeyboardButton(
                    "📈 Analytics",
                    callback_data="analytics",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔄 Refresh",
                    callback_data="refresh",
                ),
            ],
        ]
    )


# ============================================================
# AUTOREPLY KEYBOARD
# ============================================================

def autoreply_keyboard():

    settings = (
        get_autoreply_settings_runtime()
    )

    mode = settings.get(
        "mode",
        "off",
    )

    delay = settings.get(
        "delay_minutes",
        0,
    )

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🤖 Авто "
                    + (
                        "🟢"
                        if mode == "auto"
                        else ""
                    ),
                    callback_data="ar_mode_auto",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❓ Спросить разрешение "
                    + (
                        "🟢"
                        if mode == "ask"
                        else ""
                    ),
                    callback_data="ar_mode_ask",
                ),
            ],
            [
                InlineKeyboardButton(
                    "✋ Выключено "
                    + (
                        "🟢"
                        if mode == "off"
                        else ""
                    ),
                    callback_data="ar_mode_off",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"⏱ Задержка: {delay} мин.",
                    callback_data="ar_delay_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ Отменить активные ответы",
                    callback_data="ar_cancel",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="refresh",
                ),
            ],
        ]
    )


# ============================================================
# DELAY KEYBOARD
# ============================================================

def delay_keyboard():

    delays = [
        0,
        5,
        10,
        15,
        20,
        30,
        60,
    ]

    rows = []

    for i in range(
        0,
        len(delays),
        2,
    ):

        row = []

        for delay in delays[
            i:i + 2
        ]:

            row.append(
                InlineKeyboardButton(
                    f"{delay} мин.",
                    callback_data=f"ar_delay_{delay}",
                )
            )

        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="autoreply_menu",
            ),
        ]
    )

    return InlineKeyboardMarkup(
        rows
    )


# ============================================================
# STATUS TEXT
# ============================================================

def status_text() -> str:

    settings = (
        get_autoreply_settings_runtime()
    )

    mode = settings.get(
        "mode",
        "off",
    )

    delay = settings.get(
        "delay_minutes",
        0,
    )

    status = get_autoreply_status()

    pending = status.get(
        "pending_chats",
        0,
    )

    scheduled = status.get(
        "total_scheduled",
        0,
    )

    replies = status.get(
        "total_replies",
        0,
    )

    cancelled = status.get(
        "total_cancelled",
        0,
    )

    errors = status.get(
        "total_errors",
        0,
    )

    return (
        "🤖 <b>JARVIS 2.0</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Auto Reply: "
        f"<b>{autoreply_mode_text(mode)}</b>\n"
        f"⏱ Delay: "
        f"<b>{delay} мин.</b>\n"
        f"🛡 Security: "
        f"{'🟢 ON' if is_security_enabled() else '🔴 OFF'}\n"
        f"👁 Monitoring: "
        f"{'🟢 ON' if is_monitoring_enabled() else '🔴 OFF'}\n"
        f"🎛 Mode: {mode_text()}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"⏳ Active timers: {pending}\n"
        f"📨 Scheduled: {scheduled}\n"
        f"💬 Replies: {replies}\n"
        f"⏹ Cancelled: {cancelled}\n"
        f"❌ Errors: {errors}\n"
    )


# ============================================================
# START
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
# STATUS
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
# AUTOREPLY COMMAND
# ============================================================

async def cmd_autoreply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    if context.args:

        value = (
            context.args[0]
            .lower()
        )

        if value == "auto":

            await set_autoreply_settings_runtime(
                "auto",
                None,
            )

        elif value in {
            "ask",
            "question",
        }:

            await set_autoreply_settings_runtime(
                "ask",
                None,
            )

        elif value in {
            "off",
            "manual",
        }:

            await set_autoreply_settings_runtime(
                "off",
                None,
            )

        else:

            await update.message.reply_text(
                "Используй:\n\n"
                "/autoreply auto\n"
                "/autoreply ask\n"
                "/autoreply off"
            )

            return

    await update.message.reply_text(
        autoreply_status_text(),
        parse_mode="HTML",
        reply_markup=autoreply_keyboard(),
    )


# ============================================================
# SECURITY COMMAND
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
            .lower()
        )

        if value in {
            "on",
            "1",
            "true",
        }:

            set_security_enabled(
                True
            )

        elif value in {
            "off",
            "0",
            "false",
        }:

            set_security_enabled(
                False
            )

    await update.message.reply_text(
        status_text(),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# ============================================================
# MONITORING COMMAND
# ============================================================

async def cmd_monitoring(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    if context.args:

        value = (
            context.args[0]
            .lower()
        )

        if value in {
            "on",
            "1",
            "true",
        }:

            set_monitoring_enabled(
                True
            )

        elif value in {
            "off",
            "0",
            "false",
        }:

            set_monitoring_enabled(
                False
            )

    await update.message.reply_text(
        status_text(),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# ============================================================
# NORMAL COMMAND
# ============================================================

async def cmd_normal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    set_normal_mode()

    await update.message.reply_text(
        status_text(),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# ============================================================
# AGRO COMMAND
# ============================================================

async def cmd_agro(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    minutes = 30

    if context.args:

        try:

            minutes = int(
                context.args[0]
            )

        except ValueError:

            minutes = 30

    minutes = max(
        1,
        min(
            minutes,
            30,
        ),
    )

    set_agro_mode(
        minutes
    )

    await update.message.reply_text(
        status_text(),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# ============================================================
# STATISTICS COMMAND
# ============================================================

async def cmd_stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    status = get_autoreply_status()

    await update.message.reply_text(
        (
            "📊 <b>JARVIS STATISTICS</b>\n\n"
            f"📨 Scheduled: "
            f"{status.get('total_scheduled', 0)}\n"
            f"💬 Replies: "
            f"{status.get('total_replies', 0)}\n"
            f"⏹ Cancelled: "
            f"{status.get('total_cancelled', 0)}\n"
            f"❌ Errors: "
            f"{status.get('total_errors', 0)}\n"
            f"⏳ Active: "
            f"{status.get('pending_chats', 0)}"
        ),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# ============================================================
# ANALYTICS COMMAND
# ============================================================

async def cmd_analytics(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await owner_only(update):
        return

    status = get_autoreply_status()

    scheduled = status.get(
        "total_scheduled",
        0,
    )

    replies = status.get(
        "total_replies",
        0,
    )

    cancelled = status.get(
        "total_cancelled",
        0,
    )

    errors = status.get(
        "total_errors",
        0,
    )

    if scheduled:

        reply_rate = (
            replies / scheduled
        ) * 100

        cancel_rate = (
            cancelled / scheduled
        ) * 100

    else:

        reply_rate = 0
        cancel_rate = 0

    await update.message.reply_text(
        (
            "📈 <b>JARVIS ANALYTICS</b>\n\n"
            f"📨 Scheduled: {scheduled}\n"
            f"💬 Replies: {replies}\n"
            f"⏹ Cancelled: {cancelled}\n"
            f"❌ Errors: {errors}\n\n"
            f"📊 Reply rate: "
            f"{reply_rate:.1f}%\n"
            f"📉 Cancel rate: "
            f"{cancel_rate:.1f}%"
        ),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# ============================================================
# PENDING REPLY KEYBOARD
# ============================================================

def pending_reply_keyboard(
    reply_id,
):

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Разрешить",
                    callback_data=f"reply_approve:{reply_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "✏️ Изменить",
                    callback_data=f"reply_edit:{reply_id}",
                ),
                InlineKeyboardButton(
                    "❌ Отказать",
                    callback_data=f"reply_deny:{reply_id}",
                ),
            ],
        ]
    )


# ============================================================
# BUTTON HANDLER
# ============================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    global _editing_reply_id

    query = update.callback_query

    if query is None:
        return

    if query.from_user.id != OWNER_ID:

        await query.answer(
            "⛔ Доступ запрещён.",
            show_alert=True,
        )

        return

    await query.answer()

    action = query.data

    # ========================================================
    # REFRESH
    # ========================================================

    if action == "refresh":

        await query.edit_message_text(
            status_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

        return

    # ========================================================
    # AUTOREPLY MENU
    # ========================================================

    if action == "autoreply_menu":

        await query.edit_message_text(
            "🤖 <b>НАСТРОЙКИ АВТООТВЕТЧИКА</b>\n\n"
            f"{autoreply_status_text()}\n\n"
            "Выберите режим:",
            parse_mode="HTML",
            reply_markup=autoreply_keyboard(),
        )

        return

    # ========================================================
    # AUTO
    # ========================================================

    if action == "ar_mode_auto":

        settings = (
            get_autoreply_settings_runtime()
        )

        delay = settings.get(
            "delay_minutes",
            0,
        )

        await set_autoreply_settings_runtime(
            "auto",
            delay,
        )

        await query.edit_message_text(
            "🤖 <b>АВТО</b>\n\n"
            "JARVIS самостоятельно генерирует "
            "и отправляет ответы.",
            parse_mode="HTML",
            reply_markup=autoreply_keyboard(),
        )

        return

    # ========================================================
    # ASK
    # ========================================================

    if action == "ar_mode_ask":

        settings = (
            get_autoreply_settings_runtime()
        )

        delay = settings.get(
            "delay_minutes",
            0,
        )

        await set_autoreply_settings_runtime(
            "ask",
            delay,
        )

        await query.edit_message_text(
            "❓ <b>СПРОСИТЬ РАЗРЕШЕНИЕ</b>\n\n"
            "JARVIS сначала создаст предложенный "
            "ответ и отправит его тебе на проверку.\n\n"
            "Без твоего разрешения ответ не уйдёт.",
            parse_mode="HTML",
            reply_markup=autoreply_keyboard(),
        )

        return

    # ========================================================
    # OFF
    # ========================================================

    if action == "ar_mode_off":

        settings = (
            get_autoreply_settings_runtime()
        )

        delay = settings.get(
            "delay_minutes",
            0,
        )

        await set_autoreply_settings_runtime(
            "off",
            delay,
        )

        await cancel_all_autoreplies()

        await query.edit_message_text(
            "✋ <b>РУЧНОЙ РЕЖИМ</b>\n\n"
            "JARVIS больше не будет "
            "самостоятельно отвечать.",
            parse_mode="HTML",
            reply_markup=autoreply_keyboard(),
        )

        return

    # ========================================================
    # DELAY MENU
    # ========================================================

    if action == "ar_delay_menu":

        settings = (
            get_autoreply_settings_runtime()
        )

        current = settings.get(
            "delay_minutes",
            0,
        )

        await query.edit_message_text(
            "⏱ <b>ЗАДЕРЖКА АВТООТВЕТА</b>\n\n"
            f"Сейчас: <b>{current} мин.</b>\n\n"
            "Выбери время:",
            parse_mode="HTML",
            reply_markup=delay_keyboard(),
        )

        return

    # ========================================================
    # DELAY
    # ========================================================

    if action.startswith(
        "ar_delay_"
    ):

        try:

            delay = int(
                action.split("_")[-1]
            )

        except ValueError:

            delay = 0

        settings = (
            get_autoreply_settings_runtime()
        )

        mode = settings.get(
            "mode",
            "off",
        )

        await set_autoreply_settings_runtime(
            mode,
            delay,
        )

        await query.edit_message_text(
            "⏱ <b>ЗАДЕРЖКА ИЗМЕНЕНА</b>\n\n"
            f"Новое время: <b>{delay} мин.</b>",
            parse_mode="HTML",
            reply_markup=autoreply_keyboard(),
        )

        return

    # ========================================================
    # CANCEL
    # ========================================================

    if action == "ar_cancel":

        await cancel_all_autoreplies()

        await query.edit_message_text(
            "⏹ <b>АКТИВНЫЕ ОТВЕТЫ ОТМЕНЕНЫ</b>",
            parse_mode="HTML",
            reply_markup=autoreply_keyboard(),
        )

        return

    # ========================================================
    # SECURITY
    # ========================================================

    if action == "toggle_security":

        set_security_enabled(
            not is_security_enabled()
        )

        await query.edit_message_text(
            status_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

        return

    # ========================================================
    # MONITORING
    # ========================================================

    if action == "toggle_monitoring":

        set_monitoring_enabled(
            not is_monitoring_enabled()
        )

        await query.edit_message_text(
            status_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

        return

    # ========================================================
    # NORMAL
    # ========================================================

    if action == "normal":

        set_normal_mode()

        await query.edit_message_text(
            status_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

        return

    # ========================================================
    # AGRO
    # ========================================================

    if action == "agro":

        set_agro_mode(
            30
        )

        await query.edit_message_text(
            status_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

        return

    # ========================================================
    # APPROVE
    # ========================================================

    if action.startswith(
        "reply_approve:"
    ):

        try:

            reply_id = int(
                action.split(":")[1]
            )

        except ValueError:

            return

        result = await approve_pending_reply(
            reply_id
        )

        if result:

            await query.edit_message_text(
                "✅ <b>ОТВЕТ ОТПРАВЛЕН</b>\n\n"
                "JARVIS отправил предложенный ответ.",
                parse_mode="HTML",
            )

        else:

            await query.edit_message_text(
                "❌ Не удалось отправить ответ.\n"
                "Возможно, он уже обработан.",
                parse_mode="HTML",
            )

        return

    # ========================================================
    # EDIT
    # ========================================================

    if action.startswith(
        "reply_edit:"
    ):

        try:

            reply_id = int(
                action.split(":")[1]
            )

        except ValueError:

            return

        pending = await get_pending_reply(
            reply_id
        )

        if not pending:

            await query.edit_message_text(
                "❌ Ответ уже обработан."
            )

            return

        _editing_reply_id = reply_id

        await query.edit_message_text(
            "✏️ <b>ИЗМЕНЕНИЕ ОТВЕТА</b>\n\n"
            "Отправь следующим сообщением "
            "новый текст ответа.",
            parse_mode="HTML",
        )

        return

    # ========================================================
    # DENY
    # ========================================================

    if action.startswith(
        "reply_deny:"
    ):

        try:

            reply_id = int(
                action.split(":")[1]
            )

        except ValueError:

            return

        result = await deny_pending_reply(
            reply_id
        )

        if result:

            await query.edit_message_text(
                "❌ <b>ОТВЕТ ОТКЛОНЁН</b>\n\n"
                "JARVIS ничего не отправил.",
                parse_mode="HTML",
            )

        else:

            await query.edit_message_text(
                "⚠️ Ответ уже был обработан."
            )

        return

    # ========================================================
    # STATISTICS
    # ========================================================

    if action == "statistics":

        status = get_autoreply_status()

        text = (
            "📊 <b>STATISTICS</b>\n\n"
            f"📨 Scheduled: "
            f"{status.get('total_scheduled', 0)}\n"
            f"💬 Replies: "
            f"{status.get('total_replies', 0)}\n"
            f"⏹ Cancelled: "
            f"{status.get('total_cancelled', 0)}\n"
            f"❌ Errors: "
            f"{status.get('total_errors', 0)}\n"
            f"⏳ Active: "
            f"{status.get('pending_chats', 0)}"
        )

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📈 Analytics",
                            callback_data="analytics",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "⬅️ Back",
                            callback_data="refresh",
                        ),
                    ],
                ]
            ),
        )

        return

    # ========================================================
    # ANALYTICS
    # ========================================================

    if action == "analytics":

        status = get_autoreply_status()

        scheduled = status.get(
            "total_scheduled",
            0,
        )

        replies = status.get(
            "total_replies",
            0,
        )

        cancelled = status.get(
            "total_cancelled",
            0,
        )

        errors = status.get(
            "total_errors",
            0,
        )

        reply_rate = (
            (
                replies
                / scheduled
            )
            * 100
            if scheduled
            else 0
        )

        await query.edit_message_text(
            (
                "📈 <b>ANALYTICS</b>\n\n"
                f"📨 Scheduled: {scheduled}\n"
                f"💬 Replies: {replies}\n"
                f"⏹ Cancelled: {cancelled}\n"
                f"❌ Errors: {errors}\n\n"
                f"📊 Reply rate: "
                f"{reply_rate:.1f}%"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📊 Statistics",
                            callback_data="statistics",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "⬅️ Back",
                            callback_data="refresh",
                        ),
                    ],
                ]
            ),
        )

        return


# ============================================================
# EDIT TEXT HANDLER
# ============================================================

async def edit_text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    global _editing_reply_id

    if not await owner_only(update):
        return

    if _editing_reply_id is None:
        return

    text = (
        update.message.text or ""
    ).strip()

    if not text:

        await update.message.reply_text(
            "❌ Текст пустой."
        )

        return

    reply_id = _editing_reply_id

    _editing_reply_id = None

    success = await set_pending_reply_text(
        reply_id,
        text,
    )

    if not success:

        await update.message.reply_text(
            "❌ Не удалось изменить ответ."
        )

        return

    await update.message.reply_text(
        "✏️ <b>ОТВЕТ ИЗМЕНЁН</b>\n\n"
        f"💬 {text}",
        parse_mode="HTML",
        reply_markup=pending_reply_keyboard(
            reply_id
        ),
    )


# ============================================================
# START MONITOR BOT
# ============================================================

async def start_monitor_bot(
    owner_id: Optional[int] = None,
):

    global _monitor_application

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN не задан."
        )

    # ========================================================
    # LOAD AUTOREPLY SETTINGS
    # ========================================================

    settings = await get_current_settings()

    print()
    print(
        "🤖 Auto Reply settings loaded:"
    )

    print(
        f"Mode: "
        f"{settings.get('mode', 'off')}"
    )

    print(
        f"Delay: "
        f"{settings.get('delay_minutes', 0)} min."
    )

    # ========================================================
    # SECURITY STATE
    # ========================================================

    print(
        f"🛡 Security: "
        f"{'ON' if is_security_enabled() else 'OFF'}"
    )

    # ========================================================
    # MONITORING STATE
    # ========================================================

    print(
        f"📡 Monitoring: "
        f"{'ON' if is_monitoring_enabled() else 'OFF'}"
    )

    # ========================================================
    # APPLICATION
    # ========================================================

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ========================================================
    # COMMANDS
    # ========================================================

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
            "autoreply",
            cmd_autoreply,
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
            "monitoring",
            cmd_monitoring,
        )
    )

    application.add_handler(
        CommandHandler(
            "normal",
            cmd_normal,
        )
    )

    application.add_handler(
        CommandHandler(
            "agro",
            cmd_agro,
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
            "analytics",
            cmd_analytics,
        )
    )

    # ========================================================
    # BUTTONS
    # ========================================================

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # ========================================================
    # TEXT
    # ========================================================

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            edit_text_handler,
        )
    )

    # ========================================================
    # START
    # ========================================================

    await application.initialize()

    await application.start()

    if application.updater:

        await application.updater.start_polling()

    _monitor_application = application

    print()
    print(
        "=" * 60
    )
    print(
        "📡 MONITOR BOT ONLINE"
    )
    print(
        "=" * 60
    )

    return application


# ============================================================
# STOP
# ============================================================

async def stop_monitor_bot():

    global _monitor_application

    application = _monitor_application

    if application is None:
        return

    try:

        if application.updater:

            await application.updater.stop()

    except Exception as e:

        print(
            f"⚠️ Updater stop error: {e}"
        )

    try:

        await application.stop()

    except Exception as e:

        print(
            f"⚠️ Monitor stop error: {e}"
        )

    try:

        await application.shutdown()

    except Exception as e:

        print(
            f"⚠️ Monitor shutdown error: {e}"
        )

    _monitor_application = None

    print(
        "📡 MONITOR BOT OFFLINE"
    )