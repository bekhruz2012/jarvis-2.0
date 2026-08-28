import asyncio
import io
import sqlite3
import time
from collections import defaultdict, deque
from html import escape

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.functions.contacts import (
    BlockRequest,
    UnblockRequest,
)

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from config import (
    TG_API_ID,
    TG_API_HASH,
    SESSION_NAME,
    MAX_MESSAGE_CACHE,
    DATABASE_PATH,
)

from database import (
    save_user,
    save_message,
    get_message,
    mark_message_deleted,
    mark_message_edited,
    get_chat_messages,
    block_user,
    unblock_user,
    increment_stat,
)

from security import analyze_message

from ai import (
    get_mode,
    NORMAL_MODE,
    AGRO_MODE,
)

from autoreply import (
    register_incoming,
    register_owner_reply,
)


# ============================================================
# TELEGRAM CLIENT
# ============================================================

client = TelegramClient(
    SESSION_NAME,
    TG_API_ID,
    TG_API_HASH,
)


# ============================================================
# GLOBAL STATE
# ============================================================

MY_ID = None
MY_USERNAME = None
MY_NAME = None

MONITOR_BOT = None


# ============================================================
# MESSAGE CACHE
# ============================================================

_message_cache = {}

_message_cache_order = deque(
    maxlen=MAX_MESSAGE_CACHE
)


# ============================================================
# SECURITY NOTIFICATION CACHE
# ============================================================

_security_notification_cache = {}

SECURITY_NOTIFICATION_COOLDOWN = 60


# ============================================================
# DELETED MESSAGE BATCHES
# ============================================================

_deleted_batches = defaultdict(list)

_deleted_batch_tasks = {}

DELETED_BATCH_DELAY = 2


# ============================================================
# EDIT HISTORY
# ============================================================

_edit_history_ready = False


# ============================================================
# HELPERS
# ============================================================

def row_get(row, key, default=None):
    """
    Безопасно получает значение из sqlite Row,
    dict или обычного объекта.
    """

    if row is None:
        return default

    if isinstance(row, dict):
        return row.get(key, default)

    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        pass

    try:
        return getattr(row, key, default)
    except Exception:
        return default


def safe_int(value, default=None):
    """
    Безопасное преобразование в int.
    """

    try:
        if value is None:
            return default

        return int(value)

    except (ValueError, TypeError):
        return default


def safe_text(text, limit=3000):
    """
    Экранирует текст для Telegram HTML.
    """

    if text is None:
        return ""

    try:
        text = str(text)
    except Exception:
        text = ""

    if len(text) > limit:
        text = text[:limit] + "\n…"

    return escape(text)


def raw_text(text, limit=10000):
    """
    Возвращает обычный текст без HTML escape.
    """

    if text is None:
        return ""

    try:
        text = str(text)
    except Exception:
        return ""

    if len(text) > limit:
        text = text[:limit] + "\n…"

    return text


# ============================================================
# BOT
# ============================================================

def set_monitor_bot(bot):
    """
    Подключает Monitor Bot.
    """

    global MONITOR_BOT

    MONITOR_BOT = bot

    print("🤖 Monitor Bot подключён.")


# ============================================================
# USER INFO
# ============================================================

def get_display_name(sender):
    """
    Возвращает красивое имя пользователя.
    """

    if sender is None:
        return "Unknown"

    first_name = getattr(
        sender,
        "first_name",
        None,
    )

    last_name = getattr(
        sender,
        "last_name",
        None,
    )

    username = getattr(
        sender,
        "username",
        None,
    )

    title = getattr(
        sender,
        "title",
        None,
    )

    if title:
        name = str(title)

    elif first_name:
        name = str(first_name)

        if last_name:
            name += f" {last_name}"

    elif username:
        name = f"@{username}"

    else:
        sender_id = getattr(
            sender,
            "id",
            None,
        )

        name = str(
            sender_id
            if sender_id is not None
            else "Unknown"
        )

    if (
        username
        and not name.startswith("@")
        and f"@{username}" not in name
    ):
        name += f" (@{username})"

    return name


def get_user_info(sender):
    """
    Возвращает основные данные пользователя.
    """

    if sender is None:
        return {
            "id": None,
            "first_name": None,
            "last_name": None,
            "username": None,
        }

    return {
        "id": getattr(sender, "id", None),
        "first_name": getattr(
            sender,
            "first_name",
            None,
        ),
        "last_name": getattr(
            sender,
            "last_name",
            None,
        ),
        "username": getattr(
            sender,
            "username",
            None,
        ),
    }


# ============================================================
# CHAT INFO
# ============================================================

def get_chat_name(chat):
    """
    Возвращает имя чата.
    """

    if chat is None:
        return "Unknown chat"

    title = getattr(
        chat,
        "title",
        None,
    )

    if title:
        return str(title)

    first_name = getattr(
        chat,
        "first_name",
        None,
    )

    last_name = getattr(
        chat,
        "last_name",
        None,
    )

    username = getattr(
        chat,
        "username",
        None,
    )

    if first_name:

        name = str(first_name)

        if last_name:
            name += f" {last_name}"

        return name

    if username:
        return f"@{username}"

    chat_id = getattr(
        chat,
        "id",
        None,
    )

    return str(
        chat_id
        if chat_id is not None
        else "Unknown"
    )


def get_chat_type(chat):
    """
    Определяет тип Telegram чата.
    """

    if chat is None:
        return "unknown"

    if getattr(
        chat,
        "broadcast",
        False,
    ):
        return "channel"

    if getattr(
        chat,
        "megagroup",
        False,
    ):
        return "supergroup"

    if getattr(
        chat,
        "gigagroup",
        False,
    ):
        return "supergroup"

    if getattr(
        chat,
        "bot",
        False,
    ):
        return "bot"

    if getattr(
        chat,
        "user",
        False,
    ):
        return "private"

    if getattr(
        chat,
        "title",
        None,
    ):
        return "group"

    return "unknown"


# ============================================================
# MESSAGE CACHE
# ============================================================

def make_cache_key(chat_id, message_id):
    return (
        safe_int(chat_id, 0),
        safe_int(message_id, 0),
    )


def cache_message(
    chat_id,
    message_id,
    data,
):
    """
    Сохраняет сообщение в RAM cache.
    """

    key = make_cache_key(
        chat_id,
        message_id,
    )

    if key not in _message_cache:

        if (
            len(_message_cache_order)
            >= MAX_MESSAGE_CACHE
        ):

            try:
                oldest = (
                    _message_cache_order.popleft()
                )

                _message_cache.pop(
                    oldest,
                    None,
                )

            except IndexError:
                pass

        _message_cache_order.append(
            key
        )

    _message_cache[key] = data


def get_cached_message(
    chat_id,
    message_id,
):
    return _message_cache.get(
        make_cache_key(
            chat_id,
            message_id,
        )
    )


def remove_cached_message(
    chat_id,
    message_id,
):
    _message_cache.pop(
        make_cache_key(
            chat_id,
            message_id,
        ),
        None,
    )


# ============================================================
# OWNER NOTIFICATION
# ============================================================

async def notify_owner(
    text,
    buttons=None,
):
    """
    Отправляет сообщение владельцу через Monitor Bot.
    """

    if MONITOR_BOT is None:
        print(
            "⚠️ Monitor Bot ещё не подключён."
        )
        return False

    if MY_ID is None:
        print(
            "⚠️ MY_ID ещё не определён."
        )
        return False

    try:

        await MONITOR_BOT.send_message(
            chat_id=MY_ID,
            text=text,
            parse_mode="HTML",
            reply_markup=buttons,
        )

        return True

    except FloodWaitError as e:

        print(
            "⚠️ Monitor Bot FloodWait: "
            f"{getattr(e, 'seconds', 5)} sec"
        )

        return False

    except (
        asyncio.TimeoutError,
        ConnectionError,
    ) as e:

        print(
            "⚠️ Monitor Bot connection error: "
            f"{type(e).__name__}: {e}"
        )

        return False

    except Exception as e:

        print(
            "❌ Owner notification error: "
            f"{type(e).__name__}: {e}"
        )

        return False


async def send_owner_document(
    content,
    filename,
    caption=None,
):
    """
    Отправляет текстовый файл владельцу.
    """

    if MONITOR_BOT is None:
        print(
            "⚠️ Cannot send document: "
            "Monitor Bot unavailable."
        )
        return False

    if MY_ID is None:
        return False

    try:

        document = io.BytesIO(
            content.encode(
                "utf-8",
                errors="replace",
            )
        )

        document.name = filename

        await MONITOR_BOT.send_document(
            chat_id=MY_ID,
            document=document,
            caption=caption,
            parse_mode="HTML",
        )

        return True

    except (
        asyncio.TimeoutError,
        ConnectionError,
    ) as e:

        print(
            "⚠️ Document connection error: "
            f"{type(e).__name__}: {e}"
        )

        return False

    except Exception as e:

        print(
            "❌ Document send error: "
            f"{type(e).__name__}: {e}"
        )

        return False


# ============================================================
# SECURITY NOTIFICATIONS
# ============================================================

def should_send_security_notification(
    user_id,
    event_type,
):
    """
    Не позволяет спамить владельца одинаковыми
    security notifications.
    """

    now = time.time()

    key = (
        user_id,
        event_type,
    )

    last = _security_notification_cache.get(
        key,
        0,
    )

    if (
        now - last
        < SECURITY_NOTIFICATION_COOLDOWN
    ):
        return False

    _security_notification_cache[key] = now

    return True


def history_keyboard(user_id):
    """
    Inline keyboard для Security notification.
    """

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📖 Показать чат",
                    callback_data=(
                        f"history:{user_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    "🚫 Заблокировать",
                    callback_data=(
                        f"block:{user_id}"
                    ),
                )
            ],
        ]
    )


async def notify_security_block(
    sender,
    result,
    text,
):
    """
    Уведомление о блокировке.
    """

    if sender is None:
        return

    user_id = safe_int(
        getattr(sender, "id", None)
    )

    if not user_id:
        return

    event_type = result.get(
        "event_type",
        "security",
    )

    if not should_send_security_notification(
        user_id,
        event_type,
    ):
        return

    name = get_display_name(sender)

    notification = (
        "🚨 <b>JARVIS SECURITY</b>\n\n"

        f"👤 <b>{safe_text(name, 200)}</b>\n"
        f"🆔 <code>{user_id}</code>\n\n"

        f"⚠️ Тип: "
        f"<b>{safe_text(event_type, 100)}</b>\n"

        f"🛡️ Spam: "
        f"<b>{result.get('spam_score', 0)}/100</b>\n"

        f"🎣 Scam: "
        f"<b>{result.get('scam_score', 0)}/100</b>\n\n"

        f"📌 Причина:\n"
        f"{safe_text(result.get('reason', ''), 1000)}\n\n"

        f"💬 Сообщение:\n"
        f"<i>{safe_text(text, 2000)}</i>\n\n"

        "🚫 <b>Пользователь заблокирован "
        "через Telegram.</b>"
    )

    await notify_owner(
        notification,
        history_keyboard(user_id),
    )


async def notify_security_warning(
    sender,
    result,
    text,
):
    """
    Уведомление о подозрительном сообщении,
    которое пока не привело к блокировке.
    """

    if sender is None:
        return

    user_id = safe_int(
        getattr(sender, "id", None)
    )

    if not user_id:
        return

    if not should_send_security_notification(
        user_id,
        "warning",
    ):
        return

    notification = (
        "⚠️ <b>JARVIS SECURITY WARNING</b>\n\n"

        f"👤 <b>{safe_text(get_display_name(sender), 200)}</b>\n"
        f"🆔 <code>{user_id}</code>\n\n"

        f"🛡️ Spam: "
        f"<b>{result.get('spam_score', 0)}/100</b>\n"

        f"🎣 Scam: "
        f"<b>{result.get('scam_score', 0)}/100</b>\n\n"

        f"📌 Причина:\n"
        f"{safe_text(result.get('reason', ''), 1000)}\n\n"

        f"💬 Сообщение:\n"
        f"<i>{safe_text(text, 1500)}</i>\n\n"

        "⏳ Пользователь пока не заблокирован."
    )

    await notify_owner(
        notification,
        history_keyboard(user_id),
    )


# ============================================================
# EDIT HISTORY DATABASE
# ============================================================

async def init_edit_history():
    """
    Создаёт таблицу истории редактирования.
    """

    global _edit_history_ready

    if _edit_history_ready:
        return

    def initialize():

        connection = sqlite3.connect(
            DATABASE_PATH,
            timeout=30,
        )

        try:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS message_edit_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_message_id INTEGER,
                    chat_id INTEGER,
                    sender_id INTEGER,
                    sender_name TEXT,
                    old_text TEXT,
                    new_text TEXT,
                    edited_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_edit_history_message
                ON message_edit_history(
                    telegram_message_id
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_edit_history_chat
                ON message_edit_history(
                    chat_id
                )
                """
            )

            connection.commit()

        finally:
            connection.close()

    try:

        await asyncio.to_thread(
            initialize
        )

        _edit_history_ready = True

        print(
            "✏️ Edit history DB: ONLINE"
        )

    except Exception as e:

        print(
            "❌ Edit history DB error: "
            f"{type(e).__name__}: {e}"
        )


async def save_edit_history(
    message_id,
    chat_id,
    sender_id,
    sender_name,
    old_text,
    new_text,
):
    """
    Сохраняет старую и новую версию сообщения.
    """

    await init_edit_history()

    if not _edit_history_ready:
        return

    def save():

        connection = sqlite3.connect(
            DATABASE_PATH,
            timeout=30,
        )

        try:

            connection.execute(
                """
                INSERT INTO message_edit_history (
                    telegram_message_id,
                    chat_id,
                    sender_id,
                    sender_name,
                    old_text,
                    new_text
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    chat_id,
                    sender_id,
                    sender_name,
                    old_text,
                    new_text,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    try:

        await asyncio.to_thread(
            save
        )

    except Exception as e:

        print(
            "❌ Save edit history error: "
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# SECURITY PROCESSOR
# ============================================================

async def process_security(
    sender,
    sender_id,
    chat_id,
    text,
):
    """
    Полностью обрабатывает Security.

    Возвращает:
        True  -> обработка завершена, дальше не надо
        False -> можно продолжать AutoReply
    """

    if sender is None:
        return False

    if not sender_id:
        return False

    if getattr(
        sender,
        "bot",
        False,
    ):
        return False

    try:

        result = await analyze_message(
            user_id=sender_id,
            chat_id=chat_id,
            text=text,
        )

    except Exception as e:

        print(
            "❌ Security error: "
            f"{type(e).__name__}: {e}"
        )

        # Security никогда не должен ломать AutoReply.
        return False

    spam_score = result.get(
        "spam_score",
        0,
    )

    scam_score = result.get(
        "scam_score",
        0,
    )

    action = result.get(
        "action",
        "allow",
    )

    print(
        f"🛡️ Spam: {spam_score}/100"
    )

    print(
        f"🎣 Scam: {scam_score}/100"
    )

    print(
        f"⚙️ Security action: {action}"
    )

    # --------------------------------------------------------
    # BLOCK
    # --------------------------------------------------------

    if action == "block":

        blocked = False

        try:

            blocked = await block_telegram_user(
                sender_id
            )

        except Exception as e:

            print(
                "❌ Block exception: "
                f"{type(e).__name__}: {e}"
            )

        if blocked:

            try:

                await block_user(
                    sender_id,
                    result.get(
                        "reason",
                        "Security",
                    ),
                )

            except Exception as e:

                print(
                    "❌ Save block DB error: "
                    f"{type(e).__name__}: {e}"
                )

            try:

                await notify_security_block(
                    sender,
                    result,
                    text,
                )

            except Exception as e:

                print(
                    "❌ Security notification error: "
                    f"{type(e).__name__}: {e}"
                )

            return True

        # Если Telegram block не удался,
        # не прекращаем работу AutoReply.
        print(
            "⚠️ Telegram block failed; "
            "continuing message processing."
        )

        return False

    # --------------------------------------------------------
    # WARNING
    # --------------------------------------------------------

    if action == "warn":

        try:

            await notify_security_warning(
                sender,
                result,
                text,
            )

        except Exception as e:

            print(
                "❌ Warning notification error: "
                f"{type(e).__name__}: {e}"
            )

    return False


# ============================================================
# NEW MESSAGE
# ============================================================

@client.on(
    events.NewMessage(
        incoming=True
    )
)
async def new_message(event):
    """
    Главный обработчик входящих сообщений.
    """

    global MY_ID

    try:

        # ----------------------------------------------------
        # OWNER ID
        # ----------------------------------------------------

        if MY_ID is None:

            me = await client.get_me()

            if me is None:
                return

            MY_ID = me.id

        # Не обрабатываем собственные сообщения.
        if event.sender_id == MY_ID:
            return

        # ----------------------------------------------------
        # SENDER
        # ----------------------------------------------------

        sender = None

        try:

            sender = await event.get_sender()

        except Exception as e:

            print(
                "⚠️ Sender resolve error: "
                f"{type(e).__name__}: {e}"
            )

        sender_id = safe_int(
            event.sender_id
        )

        sender_name = get_display_name(
            sender
        )

        # ----------------------------------------------------
        # TEXT
        # ----------------------------------------------------

        text = (
            event.raw_text or ""
        ).strip()

        # ----------------------------------------------------
        # CHAT
        # ----------------------------------------------------

        chat = None

        try:

            chat = await event.get_chat()

        except Exception as e:

            print(
                "⚠️ Chat resolve error: "
                f"{type(e).__name__}: {e}"
            )

        chat_id = safe_int(
            event.chat_id
        )

        chat_name = get_chat_name(
            chat
        )

        chat_type = get_chat_type(
            chat
        )

        # ----------------------------------------------------
        # LOG
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("📩 NEW TELEGRAM MESSAGE")
        print(f"💬 Chat: {chat_name}")
        print(f"📂 Type: {chat_type}")
        print(f"🆔 Chat ID: {chat_id}")
        print(f"👤 Sender: {sender_name}")
        print(f"🆔 Sender ID: {sender_id}")
        print(f"💬 {text[:1000]}")

        # ----------------------------------------------------
        # SAVE USER
        # ----------------------------------------------------

        if sender is not None and sender_id:

            info = get_user_info(
                sender
            )

            try:

                await save_user(
                    user_id=sender_id,
                    first_name=info["first_name"],
                    last_name=info["last_name"],
                    username=info["username"],
                )

            except Exception as e:

                print(
                    "❌ Save user error: "
                    f"{type(e).__name__}: {e}"
                )

        # ----------------------------------------------------
        # SAVE MESSAGE
        # ----------------------------------------------------

        try:

            message_type = (
                "text"
                if text
                else "media"
            )

            username = (
                getattr(
                    sender,
                    "username",
                    None,
                )
                if sender
                else None
            )

            await save_message(
                telegram_message_id=event.id,
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                username=username,
                text=text,
                message_type=message_type,
            )

            cache_message(
                chat_id=chat_id,
                message_id=event.id,
                data={
                    "telegram_message_id": event.id,
                    "chat_id": chat_id,
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "username": username,
                    "text": text,
                    "chat_name": chat_name,
                    "chat_type": chat_type,
                },
            )

        except Exception as e:

            print(
                "❌ Save message error: "
                f"{type(e).__name__}: {e}"
            )

        # ----------------------------------------------------
        # MEDIA WITHOUT TEXT
        # ----------------------------------------------------

        if not text:
            return

        # ----------------------------------------------------
        # SECURITY
        # ----------------------------------------------------

        stop_processing = await process_security(
            sender=sender,
            sender_id=sender_id,
            chat_id=chat_id,
            text=text,
        )

        if stop_processing:
            print(
                "🚫 Message processing stopped by Security."
            )
            return

        # ----------------------------------------------------
        # AUTOREPLY
        # ----------------------------------------------------

        if event.is_private:

            try:
                await register_incoming(
                    chat_id=chat_id,
                    sender_id=sender_id,
                    text=text,
                    message_id=event.id,
                )

            except Exception as e:

                print(
                    "❌ AutoReply error: "
                    f"{type(e).__name__}: {e}"
                )

        print(
            "✅ Message processing complete."
        )

    except Exception as e:

        print()
        print(
            "🔥 NEW MESSAGE HANDLER ERROR"
        )
        print(
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# OWNER MESSAGE
# ============================================================

@client.on(
    events.NewMessage(
        outgoing=True
    )
)
async def owner_message(event):
    """
    Отслеживает сообщения владельца.
    """

    global MY_ID

    try:

        if MY_ID is None:

            me = await client.get_me()

            if me is not None:
                MY_ID = me.id

        if event.sender_id != MY_ID:
            return

        text = (
            event.raw_text or ""
        ).strip()

        if not text:
            return

        try:

            await register_owner_reply(
                event.chat_id
            )

        except Exception as e:

            print(
                "❌ AutoReply cancel error: "
                f"{type(e).__name__}: {e}"
            )

        print()
        print(
            f"📤 OWNER MESSAGE -> "
            f"{event.chat_id}"
        )

    except Exception as e:

        print(
            "🔥 OWNER MESSAGE HANDLER ERROR: "
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# EDITED MESSAGE
# ============================================================

@client.on(
    events.MessageEdited(
        incoming=True
    )
)
async def edited_message(event):
    """
    Обрабатывает изменение сообщения.
    """

    try:

        chat_id = safe_int(
            event.chat_id
        )

        message_id = safe_int(
            event.id
        )

        sender = None

        try:

            sender = await event.get_sender()

        except Exception as e:

            print(
                "⚠️ Edit sender error: "
                f"{type(e).__name__}: {e}"
            )

        chat = None

        try:

            chat = await event.get_chat()

        except Exception:
            pass

        chat_name = get_chat_name(
            chat
        )

        chat_type = get_chat_type(
            chat
        )

        sender_id = safe_int(
            event.sender_id
        )

        sender_name = get_display_name(
            sender
        )

        new_text = (
            event.raw_text or ""
        ).strip()

        # ----------------------------------------------------
        # FIND OLD MESSAGE
        # ----------------------------------------------------

        old = None

        try:

            old = await get_message(
                message_id
            )

        except Exception as e:

            print(
                "❌ DB get message error: "
                f"{type(e).__name__}: {e}"
            )

        old_text = row_get(
            old,
            "text",
            None,
        )

        # ----------------------------------------------------
        # CACHE FALLBACK
        # ----------------------------------------------------

        if old_text is None:

            cached = get_cached_message(
                chat_id,
                message_id,
            )

            if cached:
                old_text = cached.get(
                    "text"
                )

        # ----------------------------------------------------
        # NOTHING CHANGED
        # ----------------------------------------------------

        if (
            old_text is not None
            and old_text == new_text
        ):
            return

        # ----------------------------------------------------
        # SAVE HISTORY
        # ----------------------------------------------------

        await save_edit_history(
            message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            old_text=(
                old_text
                if old_text is not None
                else ""
            ),
            new_text=new_text,
        )

        # ----------------------------------------------------
        # UPDATE MAIN MESSAGE
        # ----------------------------------------------------

        try:

            await mark_message_edited(
                telegram_message_id=message_id,
                new_text=new_text,
            )

        except Exception as e:

            print(
                "❌ Mark edited error: "
                f"{type(e).__name__}: {e}"
            )

        # ----------------------------------------------------
        # UPDATE CACHE
        # ----------------------------------------------------

        cached = get_cached_message(
            chat_id,
            message_id,
        )

        if cached:
            cached["text"] = new_text

        # ----------------------------------------------------
        # NOTIFICATION
        # ----------------------------------------------------

        notification = (
            "✏️ <b>Сообщение изменено</b>\n\n"

            f"💬 Чат: "
            f"<b>{safe_text(chat_name, 200)}</b>\n"

            f"📂 Тип: "
            f"<b>{safe_text(chat_type, 50)}</b>\n"

            f"🆔 Chat ID: "
            f"<code>{chat_id}</code>\n\n"

            f"👤 <b>{safe_text(sender_name, 200)}</b>\n"

            f"🆔 User ID: "
            f"<code>{sender_id}</code>\n\n"

            f"🆔 Message ID: "
            f"<code>{message_id}</code>\n\n"

            "<b>Было:</b>\n"
            f"<i>{safe_text(old_text or '(нет данных)', 2000)}</i>\n\n"

            "<b>Стало:</b>\n"
            f"<i>{safe_text(new_text, 2000)}</i>"
        )

        await notify_owner(
            notification,
            history_keyboard(
                sender_id or chat_id
            ),
        )

        print()
        print("✏️ MESSAGE EDITED")
        print(f"💬 Chat: {chat_name}")
        print(f"🆔 Message: {message_id}")

    except Exception as e:

        print()
        print("🔥 EDIT HANDLER ERROR")
        print(
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# PROCESS DELETED MESSAGE
# ============================================================

async def process_deleted_message(
    message_id,
    chat_id=None,
):
    """
    Находит удалённое сообщение в DB/cache
    и помечает его deleted.
    """

    try:

        old = None

        try:

            old = await get_message(
                message_id
            )

        except Exception as e:

            print(
                "❌ Deleted DB error: "
                f"{type(e).__name__}: {e}"
            )

        cached = None

        if chat_id is not None:

            cached = get_cached_message(
                chat_id,
                message_id,
            )

        if old is None and cached is None:

            print(
                f"⚠️ Deleted message {message_id}: "
                "history not found."
            )

            return None

        # ----------------------------------------------------
        # EXTRACT DATA
        # ----------------------------------------------------

        if old is not None:

            stored_chat_id = row_get(
                old,
                "chat_id",
                chat_id,
            )

            sender_id = row_get(
                old,
                "sender_id",
                None,
            )

            text = row_get(
                old,
                "text",
                "",
            )

            name = row_get(
                old,
                "sender_name",
                None,
            )

            username = row_get(
                old,
                "username",
                None,
            )

            created_at = row_get(
                old,
                "created_at",
                "",
            )

        else:

            stored_chat_id = cached.get(
                "chat_id",
                chat_id,
            )

            sender_id = cached.get(
                "sender_id"
            )

            text = cached.get(
                "text",
                "",
            )

            name = cached.get(
                "sender_name"
            )

            username = cached.get(
                "username"
            )

            created_at = ""

        if stored_chat_id is not None:
            chat_id = stored_chat_id

        if not name:

            name = (
                str(sender_id)
                if sender_id
                else "Unknown"
            )

        # ----------------------------------------------------
        # MARK DELETED
        # ----------------------------------------------------

        try:

            await mark_message_deleted(
                telegram_message_id=message_id
            )

        except Exception as e:

            print(
                "❌ Mark deleted error: "
                f"{type(e).__name__}: {e}"
            )

        remove_cached_message(
            chat_id,
            message_id,
        )

        return {
            "message_id": message_id,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "sender_name": name,
            "username": username,
            "text": text,
            "created_at": created_at,
        }

    except Exception as e:

        print(
            "🔥 Process deleted message error: "
            f"{type(e).__name__}: {e}"
        )

        return None


# ============================================================
# DELETED BATCH FLUSH
# ============================================================

async def flush_deleted_batch(chat_id):
    """
    Группирует удалённые сообщения.

    <5 сообщений -> отдельные notifications.
    >=5 -> один TXT файл.
    """

    try:

        await asyncio.sleep(
            DELETED_BATCH_DELAY
        )

        messages = _deleted_batches.pop(
            chat_id,
            [],
        )

        _deleted_batch_tasks.pop(
            chat_id,
            None,
        )

        if not messages:
            return

        # ----------------------------------------------------
        # SORT
        # ----------------------------------------------------

        messages.sort(
            key=lambda item: (
                item.get(
                    "created_at",
                    "",
                ),
                item.get(
                    "message_id",
                    0,
                ),
            )
        )

        # ----------------------------------------------------
        # SMALL DELETE
        # ----------------------------------------------------

        if len(messages) < 5:

            for item in messages:

                notification = (
                    "🗑️ <b>Сообщение удалено</b>\n\n"

                    f"💬 Chat ID: "
                    f"<code>{item.get('chat_id')}</code>\n"

                    f"👤 <b>{safe_text(item.get('sender_name'), 200)}</b>\n"

                    f"🆔 User ID: "
                    f"<code>{item.get('sender_id')}</code>\n\n"

                    f"🕐 Время: "
                    f"<code>{safe_text(item.get('created_at', 'unknown'), 100)}</code>\n"

                    f"🆔 Message ID: "
                    f"<code>{item.get('message_id')}</code>\n\n"

                    "💬 <b>Было:</b>\n"
                    f"<i>{safe_text(item.get('text', ''), 3000)}</i>"
                )

                await notify_owner(
                    notification,
                    history_keyboard(
                        item.get("sender_id")
                        or item.get("chat_id")
                    ),
                )

            return

        # ----------------------------------------------------
        # LARGE DELETE -> FILE
        # ----------------------------------------------------

        lines = [
            "JARVIS — ИСТОРИЯ УДАЛЁННЫХ СООБЩЕНИЙ",
            "=" * 70,
            f"Chat ID: {chat_id}",
            f"Количество сообщений: {len(messages)}",
            "",
        ]

        for index, item in enumerate(
            messages,
            start=1,
        ):

            lines.extend(
                [
                    "-" * 70,
                    f"#{index}",
                    f"Message ID: {item.get('message_id')}",
                    f"Chat ID: {item.get('chat_id')}",
                    f"User ID: {item.get('sender_id')}",
                    f"User: {item.get('sender_name')}",
                ]
            )

            if item.get("username"):

                lines.append(
                    f"Username: @{item.get('username')}"
                )

            lines.extend(
                [
                    f"Time: {item.get('created_at')}",
                    "",
                    "Message:",
                    item.get("text", ""),
                    "",
                ]
            )

        content = "\n".join(
            lines
        )

        timestamp = int(
            time.time()
        )

        filename = (
            f"jarvis_deleted_"
            f"{chat_id}_"
            f"{timestamp}.txt"
        )

        caption = (
            "🗑️ <b>JARVIS</b>\n\n"
            f"Удалено сообщений: "
            f"<b>{len(messages)}</b>\n"
            f"Chat ID: "
            f"<code>{chat_id}</code>\n\n"
            "📄 История отправлена файлом."
        )

        await send_owner_document(
            content=content,
            filename=filename,
            caption=caption,
        )

    except Exception as e:

        print(
            "🔥 Deleted batch error: "
            f"{type(e).__name__}: {e}"
        )

    finally:

        _deleted_batch_tasks.pop(
            chat_id,
            None,
        )


# ============================================================
# DELETED MESSAGE EVENT
# ============================================================

@client.on(
    events.MessageDeleted()
)
async def deleted_message(event):
    """
    Обработчик удаления сообщений.
    """

    try:

        print()
        print(
            "🗑️ MESSAGE DELETED EVENT"
        )

        event_chat_id = safe_int(
            getattr(
                event,
                "chat_id",
                None,
            )
        )

        for message_id in event.deleted_ids:

            deleted = await process_deleted_message(
                message_id=message_id,
                chat_id=event_chat_id,
            )

            if deleted is None:
                continue

            actual_chat_id = safe_int(
                deleted.get("chat_id")
            )

            if actual_chat_id is None:

                await notify_owner(
                    (
                        "🗑️ <b>Удалено сообщение</b>\n\n"
                        f"🆔 Message ID: "
                        f"<code>{message_id}</code>\n\n"
                        "⚠️ Chat ID недоступен."
                    )
                )

                continue

            # ------------------------------------------------
            # ADD TO BATCH
            # ------------------------------------------------

            _deleted_batches[
                actual_chat_id
            ].append(
                deleted
            )

            # ------------------------------------------------
            # ONE TIMER PER CHAT
            # ------------------------------------------------

            existing_task = (
                _deleted_batch_tasks.get(
                    actual_chat_id
                )
            )

            if (
                existing_task is None
                or existing_task.done()
            ):

                task = asyncio.create_task(
                    flush_deleted_batch(
                        actual_chat_id
                    )
                )

                _deleted_batch_tasks[
                    actual_chat_id
                ] = task

    except Exception as e:

        print()
        print(
            "🔥 DELETE HANDLER ERROR"
        )

        print(
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# CHAT HISTORY
# ============================================================

def format_chat_history(
    messages,
    title="История чата",
):
    """
    Форматирует историю для Telegram HTML.
    """

    if not messages:

        return (
            "📭 <b>История пуста.</b>"
        )

    result = (
        f"📖 <b>{safe_text(title, 200)}</b>\n\n"
    )

    for item in messages:

        sender_name = row_get(
            item,
            "sender_name",
            "Unknown",
        )

        text = row_get(
            item,
            "text",
            "",
        )

        created_at = row_get(
            item,
            "created_at",
            "",
        )

        deleted = row_get(
            item,
            "deleted",
            0,
        )

        edited = row_get(
            item,
            "edited",
            0,
        )

        flags = []

        if deleted:
            flags.append(
                "🗑️ deleted"
            )

        if edited:
            flags.append(
                "✏️ edited"
            )

        flag_text = ""

        if flags:
            flag_text = (
                " "
                + " ".join(flags)
            )

        result += (
            f"👤 <b>{safe_text(sender_name, 150)}</b>"
            f"{flag_text}\n"
        )

        if created_at:

            result += (
                f"🕐 <code>"
                f"{safe_text(created_at, 100)}"
                f"</code>\n"
            )

        result += (
            f"💬 {safe_text(text, 1000)}\n\n"
        )

        if len(result) >= 3800:

            result += (
                "\n… История сокращена."
            )

            break

    return result


async def show_chat_history(
    user_id,
    limit=30,
):
    """
    Возвращает историю чата.
    """

    try:

        messages = await get_chat_messages(
            user_id,
            limit,
        )

        return format_chat_history(
            messages,
            title=f"История чата {user_id}",
        )

    except Exception as e:

        print(
            "❌ History error: "
            f"{type(e).__name__}: {e}"
        )

        return (
            "❌ Не удалось получить "
            "историю этого чата."
        )


# ============================================================
# TELEGRAM BLOCK
# ============================================================

async def block_telegram_user(user_id):
    """
    Блокирует пользователя через Telegram account.
    """

    user_id = safe_int(
        user_id
    )

    if not user_id:
        return False

    # Никогда не блокируем владельца.
    if (
        MY_ID is not None
        and user_id == MY_ID
    ):

        print(
            "🛑 Refusing to block owner."
        )

        return False

    try:

        await client(
            BlockRequest(
                id=user_id
            )
        )

        print(
            f"🚫 Telegram user blocked: {user_id}"
        )

        return True

    except FloodWaitError as e:

        print(
            "⚠️ Telegram block FloodWait: "
            f"{getattr(e, 'seconds', '?')} sec"
        )

        return False

    except RPCError as e:

        print(
            "❌ Telegram block RPC error: "
            f"{e}"
        )

        return False

    except Exception as e:

        print(
            "❌ Telegram block error: "
            f"{type(e).__name__}: {e}"
        )

        return False


async def unblock_telegram_user(user_id):
    """
    Разблокирует пользователя через Telegram.
    """

    user_id = safe_int(
        user_id
    )

    if not user_id:
        return False

    try:

        await client(
            UnblockRequest(
                id=user_id
            )
        )

        print(
            f"🔓 Telegram user unblocked: {user_id}"
        )

        return True

    except FloodWaitError as e:

        print(
            "⚠️ Telegram unblock FloodWait: "
            f"{getattr(e, 'seconds', '?')} sec"
        )

        return False

    except RPCError as e:

        print(
            "❌ Telegram unblock RPC error: "
            f"{e}"
        )

        return False

    except Exception as e:

        print(
            "❌ Telegram unblock error: "
            f"{type(e).__name__}: {e}"
        )

        return False


# ============================================================
# MANUAL BLOCK
# ============================================================

async def manual_block_user(
    user_id,
    reason="Заблокировано владельцем",
):
    """
    Ручная блокировка.
    """

    success = await block_telegram_user(
        user_id
    )

    if not success:
        return False

    try:

        await block_user(
            user_id,
            reason,
        )

    except Exception as e:

        print(
            "❌ Manual block DB error: "
            f"{type(e).__name__}: {e}"
        )

    return True


# ============================================================
# MANUAL UNBLOCK
# ============================================================

async def manual_unblock_user(user_id):
    """
    Ручная разблокировка.
    """

    success = await unblock_telegram_user(
        user_id
    )

    if not success:
        return False

    try:

        await unblock_user(
            user_id
        )

    except Exception as e:

        print(
            "❌ Manual unblock DB error: "
            f"{type(e).__name__}: {e}"
        )

    return True


# ============================================================
# PRIVATE USER
# ============================================================

async def get_private_user(user_id):
    """
    Получает Telegram entity пользователя.
    """

    try:

        entity = await client.get_entity(
            user_id
        )

    except Exception as e:

        print(
            "❌ Entity error: "
            f"{type(e).__name__}: {e}"
        )

        return None

    if getattr(
        entity,
        "bot",
        False,
    ):
        return None

    return entity


# ============================================================
# START TELEGRAM
# ============================================================

async def start_telegram():
    """
    Запускает Telegram Client.
    """

    global MY_ID
    global MY_USERNAME
    global MY_NAME

    print(
        "📱 Запускаем Telegram Client..."
    )

    await client.start()

    me = await client.get_me()

    if me is None:

        raise RuntimeError(
            "Не удалось получить Telegram аккаунт."
        )

    MY_ID = me.id

    MY_USERNAME = getattr(
        me,
        "username",
        None,
    )

    MY_NAME = getattr(
        me,
        "first_name",
        None,
    )

    await init_edit_history()

    print(
        "✅ Telegram Client: ONLINE"
    )

    print(
        f"👤 Account: {MY_NAME}"
    )

    if MY_USERNAME:

        print(
            f"📛 Username: @{MY_USERNAME}"
        )

    print(
        f"🆔 ID: {MY_ID}"
    )

    print(
        "🛡️ Security: 24/7"
    )

    print(
        "👁️ Monitoring: ALL CHATS"
    )

    print(
        "💬 Private chats: monitored"
    )

    print(
        "👥 Groups: monitored"
    )

    print(
        "👥 Supergroups: monitored"
    )

    print(
        "📢 Channels: monitored where Telegram provides events"
    )

    print(
        f"🎛️ Mode: {get_mode()}"
    )

    return me


# ============================================================
# STOP TELEGRAM
# ============================================================

async def stop_telegram():
    """
    Корректно останавливает Telegram Client.
    """

    print(
        "📱 Останавливаем Telegram..."
    )

    # --------------------------------------------------------
    # CANCEL DELETE TASKS
    # --------------------------------------------------------

    tasks = list(
        _deleted_batch_tasks.values()
    )

    _deleted_batch_tasks.clear()

    for task in tasks:

        try:

            if not task.done():
                task.cancel()

        except Exception:
            pass

    _deleted_batches.clear()

    # --------------------------------------------------------
    # DISCONNECT
    # --------------------------------------------------------

    try:

        if client.is_connected():
            await client.disconnect()

    except Exception as e:

        print(
            "⚠️ Telegram disconnect error: "
            f"{type(e).__name__}: {e}"
        )

    print(
        "📱 Telegram Client: OFFLINE"
    )


# ============================================================
# STATUS
# ============================================================

def get_telegram_status():
    """
    Возвращает состояние Telegram Client.
    """

    current_mode = get_mode()

    return {
        "connected": client.is_connected(),

        "my_id": MY_ID,

        "username": MY_USERNAME,

        "name": MY_NAME,

        "monitor_bot": (
            MONITOR_BOT is not None
        ),

        "cached_messages": len(
            _message_cache
        ),

        "deleted_batches": len(
            _deleted_batches
        ),

        "pending_deleted_tasks": len(
            _deleted_batch_tasks
        ),

        "edit_history": (
            _edit_history_ready
        ),

        "mode": current_mode,

        "normal_mode": (
            current_mode == NORMAL_MODE
        ),

        "agro_mode": (
            current_mode == AGRO_MODE
        ),
    }
