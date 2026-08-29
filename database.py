import asyncio
import os
import sqlite3
from datetime import datetime, timezone

from config import DATABASE_PATH


# ============================================================
# CONNECTION
# ============================================================

def _connect():
    """
    Создаёт новое SQLite-соединение.

    ВАЖНО:
    Каждая операция получает своё соединение.
    Это безопаснее для asyncio.to_thread().
    """

    directory = os.path.dirname(DATABASE_PATH)

    if directory:
        os.makedirs(
            directory,
            exist_ok=True,
        )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    # Более стабильная работа при нескольких потоках.
    connection.execute(
        "PRAGMA journal_mode=WAL"
    )

    connection.execute(
        "PRAGMA busy_timeout=30000"
    )

    return connection


# ============================================================
# SAFE ROW
# ============================================================

def row_to_dict(row):
    """
    Безопасно превращает sqlite3.Row в обычный dict.

    Это помогает избежать проблем вида:

        sqlite3.Row object is not JSON serializable
    """

    if row is None:
        return None

    if isinstance(row, sqlite3.Row):
        return {
            key: row[key]
            for key in row.keys()
        }

    if isinstance(row, dict):
        return dict(row)

    try:
        return dict(row)
    except Exception:
        return row


def rows_to_dicts(rows):
    """
    Преобразует список SQLite Row в список dict.
    """

    return [
        row_to_dict(row)
        for row in rows
    ]


# ============================================================
# DATABASE INIT
# ============================================================

async def init_database():
    print("💾 Инициализация Database...")

    await init_database()

    print("💾 Database tables: READY")
    
    def _init():

        conn = _connect()

        try:

            conn.executescript(
                """
                -- ============================================================
                -- USERS
                -- ============================================================

                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,

                    first_name TEXT,
                    last_name TEXT,
                    username TEXT,

                    blocked INTEGER DEFAULT 0,
                    block_reason TEXT,

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users(username);

                CREATE INDEX IF NOT EXISTS idx_users_blocked
                ON users(blocked);


                -- ============================================================
                -- CHATS
                -- ============================================================

                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,

                    title TEXT,
                    username TEXT,

                    chat_type TEXT,

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_chats_type
                ON chats(chat_type);


                -- ============================================================
                -- MESSAGES
                -- ============================================================

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    telegram_message_id INTEGER NOT NULL,

                    chat_id INTEGER NOT NULL,
                    sender_id INTEGER,

                    sender_name TEXT,
                    username TEXT,

                    text TEXT,

                    message_type TEXT DEFAULT 'text',

                    deleted INTEGER DEFAULT 0,
                    edited INTEGER DEFAULT 0,

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TEXT,
                    edited_at TEXT,

                    UNIQUE(chat_id, telegram_message_id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_sender
                ON messages(sender_id);

                CREATE INDEX IF NOT EXISTS idx_messages_chat
                ON messages(chat_id);

                CREATE INDEX IF NOT EXISTS idx_messages_telegram_id
                ON messages(telegram_message_id);

                CREATE INDEX IF NOT EXISTS idx_messages_deleted
                ON messages(deleted);

                CREATE INDEX IF NOT EXISTS idx_messages_edited
                ON messages(edited);

                CREATE INDEX IF NOT EXISTS idx_messages_created
                ON messages(created_at);


                -- ============================================================
                -- MESSAGE EDIT HISTORY
                -- ============================================================

                CREATE TABLE IF NOT EXISTS message_edits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    telegram_message_id INTEGER NOT NULL,
                    chat_id INTEGER,

                    sender_id INTEGER,
                    sender_name TEXT,

                    old_text TEXT,
                    new_text TEXT,

                    edited_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_message_edits_message
                ON message_edits(telegram_message_id);

                CREATE INDEX IF NOT EXISTS idx_message_edits_chat
                ON message_edits(chat_id);

                CREATE INDEX IF NOT EXISTS idx_message_edits_sender
                ON message_edits(sender_id);

                CREATE INDEX IF NOT EXISTS idx_message_edits_time
                ON message_edits(edited_at);


                -- ============================================================
                -- DELETED MESSAGE HISTORY
                -- ============================================================

                CREATE TABLE IF NOT EXISTS deleted_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    telegram_message_id INTEGER NOT NULL,
                    chat_id INTEGER,

                    sender_id INTEGER,
                    sender_name TEXT,
                    username TEXT,

                    text TEXT,

                    deleted_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_deleted_messages_chat
                ON deleted_messages(chat_id);

                CREATE INDEX IF NOT EXISTS idx_deleted_messages_sender
                ON deleted_messages(sender_id);

                CREATE INDEX IF NOT EXISTS idx_deleted_messages_time
                ON deleted_messages(deleted_at);

                CREATE INDEX IF NOT EXISTS idx_deleted_messages_message
                ON deleted_messages(telegram_message_id);


                -- ============================================================
                -- CONVERSATIONS
                -- ============================================================

                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER,
                    chat_id INTEGER,

                    role TEXT,
                    content TEXT,

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_conversations_user
                ON conversations(user_id);

                CREATE INDEX IF NOT EXISTS idx_conversations_chat
                ON conversations(chat_id);

                CREATE INDEX IF NOT EXISTS idx_conversations_created
                ON conversations(created_at);


                -- ============================================================
                -- SECURITY EVENTS
                -- ============================================================

                CREATE TABLE IF NOT EXISTS security_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER,
                    chat_id INTEGER,

                    event_type TEXT,

                    action TEXT,

                    spam_score INTEGER DEFAULT 0,
                    scam_score INTEGER DEFAULT 0,

                    reason TEXT,

                    message_text TEXT,

                    blocked INTEGER DEFAULT 0,

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_security_user
                ON security_events(user_id);

                CREATE INDEX IF NOT EXISTS idx_security_chat
                ON security_events(chat_id);

                CREATE INDEX IF NOT EXISTS idx_security_type
                ON security_events(event_type);

                CREATE INDEX IF NOT EXISTS idx_security_created
                ON security_events(created_at);


                -- ============================================================
                -- AUTO REPLY SETTINGS
                -- ============================================================

                CREATE TABLE IF NOT EXISTS autoreply_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),

                    mode TEXT DEFAULT 'off',

                    delay_minutes INTEGER DEFAULT 0,

                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                INSERT OR IGNORE INTO autoreply_settings (
                    id,
                    mode,
                    delay_minutes
                )
                VALUES (
                    1,
                    'off',
                    0
                );


                -- ============================================================
                -- PENDING AUTO REPLIES
                -- ============================================================

                CREATE TABLE IF NOT EXISTS pending_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    chat_id INTEGER NOT NULL,
                    user_id INTEGER,

                    incoming_message_id INTEGER,

                    suggested_text TEXT,

                    status TEXT DEFAULT 'pending',

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_pending_replies_chat
                ON pending_replies(chat_id);

                CREATE INDEX IF NOT EXISTS idx_pending_replies_status
                ON pending_replies(status);

                CREATE INDEX IF NOT EXISTS idx_pending_replies_created
                ON pending_replies(created_at);


                -- ============================================================
                -- STATISTICS
                -- ============================================================

                CREATE TABLE IF NOT EXISTS statistics (
                    key TEXT PRIMARY KEY,

                    value INTEGER DEFAULT 0
                );
                """
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(_init)

    print("💾 Database: ONLINE")


# ============================================================
# CLOSE
# ============================================================

async def close_database():

    print("💾 Database: CLOSED")


# ============================================================
# USERS
# ============================================================

async def save_user(
    user_id,
    first_name=None,
    last_name=None,
    username=None,
):

    def _save():

        conn = _connect()

        try:

            conn.execute(
                """
                INSERT INTO users (
                    user_id,
                    first_name,
                    last_name,
                    username
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    username = excluded.username,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    first_name,
                    last_name,
                    username,
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(_save)


async def block_user(
    user_id,
    reason="",
):

    def _block():

        conn = _connect()

        try:

            conn.execute(
                """
                INSERT INTO users (
                    user_id,
                    blocked,
                    block_reason
                )
                VALUES (?, 1, ?)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    blocked = 1,
                    block_reason = excluded.block_reason,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    reason,
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(_block)


async def unblock_user(
    user_id,
):

    def _unblock():

        conn = _connect()

        try:

            conn.execute(
                """
                UPDATE users

                SET
                    blocked = 0,
                    block_reason = NULL,
                    updated_at = CURRENT_TIMESTAMP

                WHERE user_id = ?
                """,
                (
                    user_id,
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(_unblock)


async def get_user(
    user_id,
):

    def _get():

        conn = _connect()

        try:

            row = conn.execute(
                """
                SELECT *
                FROM users
                WHERE user_id = ?
                """,
                (
                    user_id,
                ),
            ).fetchone()

            return row_to_dict(row)

        finally:

            conn.close()

    return await asyncio.to_thread(_get)


async def is_user_blocked(
    user_id,
):

    user = await get_user(
        user_id
    )

    if not user:
        return False

    return bool(
        user.get(
            "blocked",
            0,
        )
    )


# ============================================================
# CHATS
# ============================================================

async def save_chat(
    chat_id,
    title=None,
    username=None,
    chat_type=None,
):

    def _save():

        conn = _connect()

        try:

            conn.execute(
                """
                INSERT INTO chats (
                    chat_id,
                    title,
                    username,
                    chat_type
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(chat_id)
                DO UPDATE SET
                    title = excluded.title,
                    username = excluded.username,
                    chat_type = excluded.chat_type,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    chat_id,
                    title,
                    username,
                    chat_type,
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(_save)


async def get_chat(
    chat_id,
):

    def _get():

        conn = _connect()

        try:

            row = conn.execute(
                """
                SELECT *
                FROM chats
                WHERE chat_id = ?
                """,
                (
                    chat_id,
                ),
            ).fetchone()

            return row_to_dict(row)

        finally:

            conn.close()

    return await asyncio.to_thread(_get)


# ============================================================
# MESSAGES
# ============================================================

async def save_message(
    telegram_message_id,
    chat_id,
    sender_id,
    sender_name,
    username,
    text,
    message_type="text",
):

    def _save():

        conn = _connect()

        try:

            conn.execute(
                """
                INSERT INTO messages (
                    telegram_message_id,
                    chat_id,
                    sender_id,
                    sender_name,
                    username,
                    text,
                    message_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(chat_id, telegram_message_id)
                DO UPDATE SET
                    sender_id = excluded.sender_id,
                    sender_name = excluded.sender_name,
                    username = excluded.username,
                    text = excluded.text,
                    message_type = excluded.message_type
                """,
                (
                    telegram_message_id,
                    chat_id,
                    sender_id,
                    sender_name,
                    username,
                    text,
                    message_type,
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(_save)


async def get_message(
    telegram_message_id,
    chat_id=None,
):

    def _get():

        conn = _connect()

        try:

            if chat_id is not None:

                row = conn.execute(
                    """
                    SELECT *
                    FROM messages

                    WHERE
                        telegram_message_id = ?
                        AND chat_id = ?

                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        telegram_message_id,
                        chat_id,
                    ),
                ).fetchone()

            else:

                row = conn.execute(
                    """
                    SELECT *
                    FROM messages

                    WHERE telegram_message_id = ?

                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        telegram_message_id,
                    ),
                ).fetchone()

            return row_to_dict(row)

        finally:

            conn.close()

    return await asyncio.to_thread(_get)


# ============================================================
# EDIT MESSAGE
# ============================================================

async def mark_message_edited(
    telegram_message_id,
    new_text,
    chat_id=None,
    sender_id=None,
    sender_name=None,
):

    def _edit():

        conn = _connect()

        try:

            # Получаем старую версию.
            if chat_id is not None:

                old = conn.execute(
                    """
                    SELECT *
                    FROM messages

                    WHERE
                        telegram_message_id = ?
                        AND chat_id = ?

                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        telegram_message_id,
                        chat_id,
                    ),
                ).fetchone()

            else:

                old = conn.execute(
                    """
                    SELECT *
                    FROM messages

                    WHERE telegram_message_id = ?

                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        telegram_message_id,
                    ),
                ).fetchone()

            old_dict = row_to_dict(old)

            old_text = ""

            if old_dict:
                old_text = old_dict.get(
                    "text",
                    "",
                )

                if chat_id is None:
                    chat_id_value = old_dict.get(
                        "chat_id"
                    )
                else:
                    chat_id_value = chat_id

                if sender_id is None:
                    sender_id_value = old_dict.get(
                        "sender_id"
                    )
                else:
                    sender_id_value = sender_id

                if sender_name is None:
                    sender_name_value = old_dict.get(
                        "sender_name"
                    )
                else:
                    sender_name_value = sender_name

            else:

                chat_id_value = chat_id
                sender_id_value = sender_id
                sender_name_value = sender_name

            # Сохраняем историю.
            conn.execute(
                """
                INSERT INTO message_edits (
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
                    telegram_message_id,
                    chat_id_value,
                    sender_id_value,
                    sender_name_value,
                    old_text,
                    new_text,
                ),
            )

            # Обновляем текущее сообщение.
            if chat_id is not None:

                conn.execute(
                    """
                    UPDATE messages

                    SET
                        text = ?,
                        edited = 1,
                        edited_at = CURRENT_TIMESTAMP

                    WHERE
                        telegram_message_id = ?
                        AND chat_id = ?
                    """,
                    (
                        new_text,
                        telegram_message_id,
                        chat_id,
                    ),
                )

            else:

                conn.execute(
                    """
                    UPDATE messages

                    SET
                        text = ?,
                        edited = 1,
                        edited_at = CURRENT_TIMESTAMP

                    WHERE telegram_message_id = ?
                    """,
                    (
                        new_text,
                        telegram_message_id,
                    ),
                )

            conn.commit()

            return old_text

        finally:

            conn.close()

    return await asyncio.to_thread(_edit)


async def get_message_edit_history(
    telegram_message_id,
    limit=50,
):

    def _get():

        conn = _connect()

        try:

            rows = conn.execute(
                """
                SELECT *

                FROM message_edits

                WHERE telegram_message_id = ?

                ORDER BY id DESC

                LIMIT ?
                """,
                (
                    telegram_message_id,
                    limit,
                ),
            ).fetchall()

            return rows_to_dicts(
                rows
            )

        finally:

            conn.close()

    return await asyncio.to_thread(_get)


# ============================================================
# DELETE MESSAGE
# ============================================================

async def mark_message_deleted(
    telegram_message_id,
    chat_id=None,
):

    def _delete():

        conn = _connect()

        try:

            if chat_id is not None:

                old = conn.execute(
                    """
                    SELECT *
                    FROM messages

                    WHERE
                        telegram_message_id = ?
                        AND chat_id = ?

                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        telegram_message_id,
                        chat_id,
                    ),
                ).fetchone()

            else:

                old = conn.execute(
                    """
                    SELECT *
                    FROM messages

                    WHERE telegram_message_id = ?

                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        telegram_message_id,
                    ),
                ).fetchone()

            old_dict = row_to_dict(
                old
            )

            if old_dict is None:

                return None

            # Сохраняем полноценную историю удаления.
            conn.execute(
                """
                INSERT INTO deleted_messages (
                    telegram_message_id,
                    chat_id,
                    sender_id,
                    sender_name,
                    username,
                    text
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    telegram_message_id,
                    old_dict.get(
                        "chat_id"
                    ),
                    old_dict.get(
                        "sender_id"
                    ),
                    old_dict.get(
                        "sender_name"
                    ),
                    old_dict.get(
                        "username"
                    ),
                    old_dict.get(
                        "text",
                        "",
                    ),
                ),
            )

            # Помечаем оригинальное сообщение.
            if chat_id is not None:

                conn.execute(
                    """
                    UPDATE messages

                    SET
                        deleted = 1,
                        deleted_at = CURRENT_TIMESTAMP

                    WHERE
                        telegram_message_id = ?
                        AND chat_id = ?
                    """,
                    (
                        telegram_message_id,
                        chat_id,
                    ),
                )

            else:

                conn.execute(
                    """
                    UPDATE messages

                    SET
                        deleted = 1,
                        deleted_at = CURRENT_TIMESTAMP

                    WHERE telegram_message_id = ?
                    """,
                    (
                        telegram_message_id,
                    ),
                )

            conn.commit()

            return old_dict

        finally:

            conn.close()

    return await asyncio.to_thread(_delete)


async def get_deleted_messages(
    chat_id=None,
    sender_id=None,
    limit=100,
):

    def _get():

        conn = _connect()

        try:

            conditions = []
            params = []

            if chat_id is not None:

                conditions.append(
                    "chat_id = ?"
                )

                params.append(
                    chat_id
                )

            if sender_id is not None:

                conditions.append(
                    "sender_id = ?"
                )

                params.append(
                    sender_id
                )

            where = ""

            if conditions:

                where = (
                    "WHERE "
                    + " AND ".join(
                        conditions
                    )
                )

            query = f"""
                SELECT *

                FROM deleted_messages

                {where}

                ORDER BY id DESC

                LIMIT ?
            """

            params.append(
                limit
            )

            rows = conn.execute(
                query,
                params,
            ).fetchall()

            return rows_to_dicts(
                rows
            )

        finally:

            conn.close()

    return await asyncio.to_thread(_get)


# ============================================================
# CHAT HISTORY
# ============================================================

async def get_chat_messages(
    user_id,
    limit=30,
):

    def _get():

        conn = _connect()

        try:

            rows = conn.execute(
                """
                SELECT *
                FROM messages

                WHERE
                    sender_id = ?
                    OR chat_id = ?

                ORDER BY id DESC

                LIMIT ?
                """,
                (
                    user_id,
                    user_id,
                    limit,
                ),
            ).fetchall()

            rows = list(
                reversed(rows)
            )

            return rows_to_dicts(
                rows
            )

        finally:

            conn.close()

    return await asyncio.to_thread(_get)


async def get_messages_by_chat(
    chat_id,
    limit=100,
):

    def _get():

        conn = _connect()

        try:

            rows = conn.execute(
                """
                SELECT *

                FROM messages

                WHERE chat_id = ?

                ORDER BY id DESC

                LIMIT ?
                """,
                (
                    chat_id,
                    limit,
                ),
            ).fetchall()

            return rows_to_dicts(
                list(
                    reversed(rows)
                )
            )

        finally:

            conn.close()

    return await asyncio.to_thread(_get)


# ============================================================
# CONVERSATION
# ============================================================

async def get_conversation(
    user_id,
    limit=40,
):

    def _get():

        conn = _connect()

        try:

            rows = conn.execute(
                """
                SELECT
                    role,
                    content

                FROM conversations

                WHERE user_id = ?

                ORDER BY id DESC

                LIMIT ?
                """,
                (
                    user_id,
                    limit,
                ),
            ).fetchall()

            rows = list(
                reversed(rows)
            )

            return [
                {
                    "role": row["role"],
                    "content": row["content"],
                }
                for row in rows
            ]

        finally:

            conn.close()

    return await asyncio.to_thread(_get)


async def save_conversation(
    user_id,
    role,
    content,
    chat_id=None,
):

    def _save():

        conn = _connect()

        try:

            conn.execute(
                """
                INSERT INTO conversations (
                    user_id,
                    chat_id,
                    role,
                    content
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    chat_id,
                    role,
                    content,
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(_save)


# ============================================================
# SECURITY
# ============================================================

async def save_security_event(
    user_id,
    chat_id,
    event_type,
    action,
    spam_score=0,
    scam_score=0,
    reason="",
    message_text="",
    blocked=0,
):

    def _save():

        conn = _connect()

        try:

            conn.execute(
                """
                INSERT INTO security_events (
                    user_id,
                    chat_id,
                    event_type,
                    action,
                    spam_score,
                    scam_score,
                    reason,
                    message_text,
                    blocked
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    chat_id,
                    event_type,
                    action,
                    spam_score,
                    scam_score,
                    reason,
                    message_text,
                    blocked,
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(_save)


async def get_security_events(
    user_id=None,
    limit=100,
):

    def _get():

        conn = _connect()

        try:

            if user_id is None:

                rows = conn.execute(
                    """
                    SELECT *

                    FROM security_events

                    ORDER BY id DESC

                    LIMIT ?
                    """,
                    (
                        limit,
                    ),
                ).fetchall()

            else:

                rows = conn.execute(
                    """
                    SELECT *

                    FROM security_events

                    WHERE user_id = ?

                    ORDER BY id DESC

                    LIMIT ?
                    """,
                    (
                        user_id,
                        limit,
                    ),
                ).fetchall()

            return rows_to_dicts(
                rows
            )

        finally:

            conn.close()

    return await asyncio.to_thread(_get)


# ============================================================
# AUTO REPLY SETTINGS
# ============================================================

VALID_AUTOREPLY_MODES = {
    "auto",
    "ask",
    "off",
}

VALID_AUTOREPLY_DELAYS = {
    0,
    5,
    10,
    15,
    20,
    30,
    60,
}


async def get_autoreply_settings():

    def _get():

        conn = _connect()

        try:

            row = conn.execute(
                """
                SELECT
                    mode,
                    delay_minutes,
                    updated_at

                FROM autoreply_settings

                WHERE id = 1
                """
            ).fetchone()

            if row is None:

                return {
                    "mode": "off",
                    "delay_minutes": 0,
                    "updated_at": None,
                }

            return row_to_dict(
                row
            )

        finally:

            conn.close()

    return await asyncio.to_thread(_get)


async def set_autoreply_mode(
    mode,
):

    if mode not in VALID_AUTOREPLY_MODES:

        raise ValueError(
            f"Invalid Auto Reply mode: {mode}"
        )

    def _set():

        conn = _connect()

        try:

            conn.execute(
                """
                INSERT INTO autoreply_settings (
                    id,
                    mode,
                    delay_minutes
                )
                VALUES (
                    1,
                    ?,
                    0
                )

                ON CONFLICT(id)
                DO UPDATE SET
                    mode = excluded.mode,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    mode,
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(_set)


async def set_autoreply_delay(
    delay_minutes,
):

    delay_minutes = int(
        delay_minutes
    )

    if delay_minutes not in VALID_AUTOREPLY_DELAYS:

        raise ValueError(
            "Недопустимая задержка Auto Reply."
        )

    def _set():

        conn = _connect()

        try:

            conn.execute(
                """
                INSERT INTO autoreply_settings (
                    id,
                    mode,
                    delay_minutes
                )
                VALUES (
                    1,
                    'off',
                    ?
                )

                ON CONFLICT(id)
                DO UPDATE SET
                    delay_minutes = excluded.delay_minutes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    delay_minutes,
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(_set)


async def set_autoreply_settings(
    mode,
    delay_minutes,
):

    if mode not in VALID_AUTOREPLY_MODES:

        raise ValueError(
            f"Invalid Auto Reply mode: {mode}"
        )

    delay_minutes = int(
        delay_minutes
    )

    if delay_minutes not in VALID_AUTOREPLY_DELAYS:

        raise ValueError(
            "Недопустимая задержка Auto Reply."
        )

    def _set():

        conn = _connect()

        try:

            conn.execute(
                """
                INSERT INTO autoreply_settings (
                    id,
                    mode,
                    delay_minutes
                )
                VALUES (
                    1,
                    ?,
                    ?
                )

                ON CONFLICT(id)
                DO UPDATE SET
                    mode = excluded.mode,
                    delay_minutes = excluded.delay_minutes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    mode,
                    delay_minutes,
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(_set)


# ============================================================
# PENDING REPLIES
# ============================================================

async def create_pending_reply(
    chat_id,
    user_id,
    incoming_message_id,
    suggested_text,
):

    def _create():

        conn = _connect()

        try:

            cursor = conn.execute(
                """
                INSERT INTO pending_replies (
                    chat_id,
                    user_id,
                    incoming_message_id,
                    suggested_text,
                    status
                )
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (
                    chat_id,
                    user_id,
                    incoming_message_id,
                    suggested_text,
                ),
            )

            conn.commit()

            return cursor.lastrowid

        finally:

            conn.close()

    return await asyncio.to_thread(
        _create
    )


async def get_pending_reply(
    reply_id,
):

    def _get():

        conn = _connect()

        try:

            row = conn.execute(
                """
                SELECT *

                FROM pending_replies

                WHERE id = ?
                """,
                (
                    reply_id,
                ),
            ).fetchone()

            return row_to_dict(
                row
            )

        finally:

            conn.close()

    return await asyncio.to_thread(
        _get
    )


async def update_pending_reply(
    reply_id,
    suggested_text=None,
    status=None,
):

    def _update():

        conn = _connect()

        try:

            current = conn.execute(
                """
                SELECT *

                FROM pending_replies

                WHERE id = ?
                """,
                (
                    reply_id,
                ),
            ).fetchone()

            if current is None:
                return False

            current = row_to_dict(
                current
            )

            new_text = (
                suggested_text
                if suggested_text is not None
                else current.get(
                    "suggested_text"
                )
            )

            new_status = (
                status
                if status is not None
                else current.get(
                    "status"
                )
            )

            conn.execute(
                """
                UPDATE pending_replies

                SET
                    suggested_text = ?,
                    status = ?,
                    updated_at = CURRENT_TIMESTAMP

                WHERE id = ?
                """,
                (
                    new_text,
                    new_status,
                    reply_id,
                ),
            )

            conn.commit()

            return True

        finally:

            conn.close()

    return await asyncio.to_thread(
        _update
    )


async def get_pending_replies(
    status="pending",
    limit=100,
):

    def _get():

        conn = _connect()

        try:

            rows = conn.execute(
                """
                SELECT *

                FROM pending_replies

                WHERE status = ?

                ORDER BY id DESC

                LIMIT ?
                """,
                (
                    status,
                    limit,
                ),
            ).fetchall()

            return rows_to_dicts(
                rows
            )

        finally:

            conn.close()

    return await asyncio.to_thread(
        _get
    )


# ============================================================
# STATISTICS
# ============================================================

async def increment_stat(
    key,
    amount=1,
):

    def _increment():

        conn = _connect()

        try:

            conn.execute(
                """
                INSERT INTO statistics (
                    key,
                    value
                )
                VALUES (?, ?)

                ON CONFLICT(key)
                DO UPDATE SET
                    value =
                        value + excluded.value
                """,
                (
                    key,
                    amount,
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(
        _increment
    )


async def get_statistics():

    def _get():

        conn = _connect()

        try:

            rows = conn.execute(
                """
                SELECT
                    key,
                    value

                FROM statistics

                ORDER BY key
                """
            ).fetchall()

            return {
                row["key"]: row["value"]
                for row in rows
            }

        finally:

            conn.close()

    return await asyncio.to_thread(
        _get
    )


# ============================================================
# DATABASE CLEANUP
# ============================================================

async def cleanup_old_data(
    days=90,
):

    """
    Удаляет старые технические записи.

    Основная история сообщений не удаляется.
    """

    days = int(days)

    def _cleanup():

        conn = _connect()

        try:

            conn.execute(
                """
                DELETE FROM security_events

                WHERE created_at <
                    datetime(
                        'now',
                        ?
                    )
                """,
                (
                    f"-{days} days",
                ),
            )

            conn.execute(
                """
                DELETE FROM message_edits

                WHERE edited_at <
                    datetime(
                        'now',
                        ?
                    )
                """,
                (
                    f"-{days} days",
                ),
            )

            conn.commit()

        finally:

            conn.close()

    await asyncio.to_thread(
        _cleanup
    )


# ============================================================
# DATABASE HEALTH
# ============================================================

async def database_health():

    def _health():

        conn = _connect()

        try:

            conn.execute(
                "SELECT 1"
            ).fetchone()

            return True

        except Exception:

            return False

        finally:

            conn.close()

    return await asyncio.to_thread(
        _health
    )