from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ============================================================
# MAIN MENU
# ============================================================

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📊 Статус",
                callback_data="status"
            ),
            InlineKeyboardButton(
                "📈 Статистика",
                callback_data="stats"
            ),
        ],
        [
            InlineKeyboardButton(
                "🤖 Автоответ",
                callback_data="autoreply_menu"
            ),
        ],
        [
            InlineKeyboardButton(
                "🛡️ Security",
                callback_data="security_menu"
            ),
        ],
        [
            InlineKeyboardButton(
                "👁️ Мониторинг",
                callback_data="monitor_menu"
            ),
        ],
        [
            InlineKeyboardButton(
                "🟢 Normal",
                callback_data="mode:normal"
            ),
            InlineKeyboardButton(
                "🔴 Agro",
                callback_data="mode:agro"
            ),
        ],
    ])


# ============================================================
# AUTO REPLY MENU
# ============================================================

def autoreply_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🤖 Авто",
                callback_data="autoreply_mode:auto"
            ),
        ],
        [
            InlineKeyboardButton(
                "❓ Спросить разрешение",
                callback_data="autoreply_mode:ask"
            ),
        ],
        [
            InlineKeyboardButton(
                "✋ Выключено",
                callback_data="autoreply_mode:off"
            ),
        ],
        [
            InlineKeyboardButton(
                "⏱️ Задержка",
                callback_data="autoreply_delay_menu"
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="menu"
            ),
        ],
    ])


# ============================================================
# AUTO REPLY DELAY
# ============================================================

def autoreply_delay_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⚡ 0 минут",
                callback_data="autoreply_delay:0"
            ),
            InlineKeyboardButton(
                "⏱️ 5 минут",
                callback_data="autoreply_delay:300"
            ),
        ],
        [
            InlineKeyboardButton(
                "⏱️ 10 минут",
                callback_data="autoreply_delay:600"
            ),
            InlineKeyboardButton(
                "⏱️ 15 минут",
                callback_data="autoreply_delay:900"
            ),
        ],
        [
            InlineKeyboardButton(
                "⏱️ 20 минут",
                callback_data="autoreply_delay:1200"
            ),
            InlineKeyboardButton(
                "⏱️ 30 минут",
                callback_data="autoreply_delay:1800"
            ),
        ],
        [
            InlineKeyboardButton(
                "⏱️ 60 минут",
                callback_data="autoreply_delay:3600"
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="autoreply_menu"
            ),
        ],
    ])


# ============================================================
# ASK PERMISSION
# ============================================================

def permission_keyboard(request_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Разрешить",
                callback_data=f"reply_allow:{request_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "✏️ Изменить",
                callback_data=f"reply_edit:{request_id}"
            ),
            InlineKeyboardButton(
                "❌ Отказать",
                callback_data=f"reply_deny:{request_id}"
            ),
        ],
    ])


# ============================================================
# SECURITY MENU
# ============================================================

def security_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛡️ Вкл / Выкл Security",
                callback_data="security:toggle"
            ),
        ],
        [
            InlineKeyboardButton(
                "🚫 Автоблокировка",
                callback_data="security:autoblock"
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Security Status",
                callback_data="security:status"
            ),
        ],
        [
            InlineKeyboardButton(
                "🧹 Очистить историю",
                callback_data="security:clear"
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="menu"
            ),
        ],
    ])


# ============================================================
# MONITOR MENU
# ============================================================

def monitor_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👁️ Все чаты",
                callback_data="monitor:all"
            ),
        ],
        [
            InlineKeyboardButton(
                "🗑️ Удалённые сообщения",
                callback_data="monitor:deleted"
            ),
        ],
        [
            InlineKeyboardButton(
                "✏️ Изменения сообщений",
                callback_data="monitor:edited"
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Статус мониторинга",
                callback_data="monitor:status"
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="menu"
            ),
        ],
    ])


# ============================================================
# HISTORY
# ============================================================

def history_keyboard(user_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📖 Показать чат",
                callback_data=f"history:{user_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "🚫 Заблокировать",
                callback_data=f"block:{user_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="menu"
            ),
        ],
    ])


# ============================================================
# HISTORY CONTROLS
# ============================================================

def history_controls(user_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚫 Заблокировать",
                callback_data=f"block:{user_id}"
            ),
            InlineKeyboardButton(
                "🔓 Разблокировать",
                callback_data=f"unblock:{user_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "📖 Показать чат",
                callback_data=f"history:{user_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="menu"
            ),
        ],
    ])


# ============================================================
# SECURITY ALERT
# ============================================================

def security_alert_keyboard(user_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚫 Заблокировать",
                callback_data=f"block:{user_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔓 Не блокировать",
                callback_data=f"unblock:{user_id}"
            ),
        ],
    ])


# ============================================================
# DELETED MESSAGE
# ============================================================

def deleted_message_keyboard(chat_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📖 Открыть историю",
                callback_data=f"deleted_history:{chat_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="menu"
            ),
        ],
    ])


# ============================================================
# EDITED MESSAGE
# ============================================================

def edited_message_keyboard(chat_id, message_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📖 История изменений",
                callback_data=f"edit_history:{chat_id}:{message_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="menu"
            ),
        ],
    ])


# ============================================================
# BACK
# ============================================================

def back_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="menu"
            ),
        ],
    ])
