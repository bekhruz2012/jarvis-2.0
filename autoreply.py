import asyncio
import time

from database import (
    get_autoreply_settings,
    set_autoreply_settings,
    create_pending_reply,
    get_pending_reply as db_get_pending_reply,
    update_pending_reply,
)

from ai import ask_jarvis


# ============================================================
# CONSTANTS
# ============================================================

VALID_MODES = {
    "auto",
    "ask",
    "off",
}

VALID_DELAYS = {
    0,
    5,
    10,
    15,
    20,
    30,
    60,
}


# ============================================================
# RUNTIME
# ============================================================

_pending_tasks: dict[int, asyncio.Task] = {}

_pending_messages: dict[int, dict] = {}

_total_scheduled = 0
_total_replies = 0
_total_cancelled = 0
_total_errors = 0


# ============================================================
# RUNTIME SETTINGS CACHE
# ============================================================

_runtime_settings = {
    "mode": "off",
    "delay_minutes": 0,
}


# ============================================================
# SETTINGS
# ============================================================

async def _load_settings():

    global _runtime_settings

    try:

        settings = await get_autoreply_settings()

        if not isinstance(
            settings,
            dict,
        ):

            settings = {}

        mode = settings.get(
            "mode",
            "off",
        )

        delay = settings.get(
            "delay_minutes",
            0,
        )

        if mode not in VALID_MODES:

            mode = "off"

        try:

            delay = int(delay)

        except (
            TypeError,
            ValueError,
        ):

            delay = 0

        if delay not in VALID_DELAYS:

            delay = 0

        _runtime_settings = {
            "mode": mode,
            "delay_minutes": delay,
        }

        return dict(
            _runtime_settings
        )

    except Exception as e:

        print(
            "❌ AutoReply settings error: "
            f"{type(e).__name__}: {e}"
        )

        return dict(
            _runtime_settings
        )


# ============================================================
# SYNC SETTINGS FOR UI
# ============================================================

def get_autoreply_settings_sync():

    return dict(
        _runtime_settings
    )


def get_autoreply_settings_runtime():

    return dict(
        _runtime_settings
    )


# ============================================================
# CURRENT SETTINGS
# ============================================================

async def get_current_settings():

    return await _load_settings()


# ============================================================
# SET SETTINGS
# ============================================================

async def set_autoreply_settings_runtime(
    mode,
    delay_minutes=None,
):

    global _runtime_settings

    if mode not in VALID_MODES:

        raise ValueError(
            f"Invalid Auto Reply mode: {mode}"
        )

    # --------------------------------------------------------
    # GET CURRENT SETTINGS
    # --------------------------------------------------------

    current = await _load_settings()

    # --------------------------------------------------------
    # DELAY
    # --------------------------------------------------------

    if delay_minutes is None:

        delay_minutes = current.get(
            "delay_minutes",
            0,
        )

    try:

        delay_minutes = int(
            delay_minutes
        )

    except (
        TypeError,
        ValueError,
    ):

        delay_minutes = 0

    if delay_minutes not in VALID_DELAYS:

        raise ValueError(
            "Недопустимая задержка."
        )

    # --------------------------------------------------------
    # SAVE DATABASE
    # --------------------------------------------------------

    await set_autoreply_settings(
        mode,
        delay_minutes,
    )

    # --------------------------------------------------------
    # UPDATE CACHE
    # --------------------------------------------------------

    _runtime_settings = {
        "mode": mode,
        "delay_minutes": delay_minutes,
    }

    print()
    print(
        "🤖 AUTOREPLY SETTINGS"
    )
    print(
        f"Mode: {mode}"
    )
    print(
        f"Delay: {delay_minutes} min"
    )

    # --------------------------------------------------------
    # OFF
    # --------------------------------------------------------

    if mode == "off":

        await cancel_all_autoreplies()

    return dict(
        _runtime_settings
    )


# ============================================================
# STATUS
# ============================================================

def get_autoreply_status():

    now = time.time()

    timers = []

    for chat_id, data in list(
        _pending_messages.items()
    ):

        task = _pending_tasks.get(
            chat_id
        )

        if task is None:
            continue

        if task.done():
            continue

        created_at = data.get(
            "created_at",
            now,
        )

        delay = data.get(
            "delay",
            0,
        )

        elapsed = (
            now - created_at
        )

        remaining = max(
            0,
            delay - elapsed,
        )

        timers.append(
            {
                "chat_id": chat_id,
                "sender_id": data.get(
                    "sender_id"
                ),
                "text": data.get(
                    "text",
                    "",
                ),
                "remaining": int(
                    remaining
                ),
            }
        )

    return {
        "mode": _runtime_settings.get(
            "mode",
            "off",
        ),
        "pending_chats": len(timers),
        "total_scheduled": _total_scheduled,
        "total_replies": _total_replies,
        "total_cancelled": _total_cancelled,
        "total_errors": _total_errors,
        "timers": timers,
    }


# ============================================================
# CANCEL ONE
# ============================================================

def _cancel_task(
    chat_id: int,
):

    global _total_cancelled

    task = _pending_tasks.pop(
        chat_id,
        None,
    )

    _pending_messages.pop(
        chat_id,
        None,
    )

    if task is None:

        return False

    if not task.done():

        task.cancel()

        _total_cancelled += 1

        return True

    return False


# ============================================================
# CANCEL AUTOREPLY
# ============================================================

async def cancel_autoreply(
    chat_id: int,
):

    if not chat_id:
        return

    cancelled = _cancel_task(
        chat_id
    )

    if cancelled:

        print(
            f"⏹ Auto Reply cancelled: "
            f"{chat_id}"
        )


# ============================================================
# CANCEL ALL
# ============================================================

async def cancel_all_autoreplies():

    tasks = list(
        _pending_tasks.values()
    )

    active = [
        task
        for task in tasks
        if not task.done()
    ]

    for task in active:

        try:

            task.cancel()

        except Exception:
            pass

    if active:

        await asyncio.gather(
            *active,
            return_exceptions=True,
        )

    _pending_tasks.clear()

    _pending_messages.clear()

    print(
        "⏹️ All Auto Reply timers cancelled."
    )


# ============================================================
# OWNER REPLY
# ============================================================

async def register_owner_reply(
    chat_id: int,
):

    await cancel_autoreply(
        chat_id
    )


# ============================================================
# CURRENT MESSAGE CHECK
# ============================================================

def _is_current_message(
    chat_id,
    sender_id,
    text,
):

    current = _pending_messages.get(
        chat_id
    )

    if current is None:

        return False

    return (
        current.get("sender_id")
        == sender_id
        and
        current.get("text")
        == text
    )


# ============================================================
# GENERATE ANSWER
# ============================================================

async def _generate_answer(
    sender_id,
    text,
):

    extra_context = (
        "Это ответ от имени владельца JARVIS.\n"
        "Ответь естественно, коротко и по делу.\n"
        "Не упоминай внутреннюю архитектуру.\n"
        "Не говори, что ты человек.\n"
        "Не упоминай таймер."
    )

    return await ask_jarvis(
        user_id=sender_id,
        text=text,
        extra_context=extra_context,
    )


# ============================================================
# SEND APPROVAL REQUEST
# ============================================================

async def _send_approval_request(
    reply_id,
    chat_id,
    sender_id,
    text,
    answer,
):

    try:

        from telethon_client import (
            notify_owner,
        )

        from monitor_bot import (
            pending_reply_keyboard,
        )

        notification = (
            "❓ <b>JARVIS — НУЖНО РАЗРЕШЕНИЕ</b>\n\n"
            f"💬 Chat ID: "
            f"<code>{chat_id}</code>\n"
            f"👤 User ID: "
            f"<code>{sender_id}</code>\n\n"
            "<b>Сообщение:</b>\n"
            f"<i>{str(text)[:1500]}</i>\n\n"
            "<b>Предложенный ответ:</b>\n"
            f"<i>{str(answer)[:2500]}</i>\n\n"
            "Выбери действие:"
        )

        await notify_owner(
            notification,
            pending_reply_keyboard(
                reply_id
            ),
        )

    except Exception as e:

        print(
            "❌ Ask mode notification error: "
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# WORKER
# ============================================================

async def _worker(
    chat_id,
    sender_id,
    text,
    delay,
):

    global _total_replies
    global _total_errors

    current_task = asyncio.current_task()

    try:

        # ----------------------------------------------------
        # SETTINGS
        # ----------------------------------------------------

        settings = await _load_settings()

        mode = settings.get(
            "mode",
            "off",
        )

        # ----------------------------------------------------
        # OFF
        # ----------------------------------------------------

        if mode == "off":

            return

        # ----------------------------------------------------
        # DELAY
        # ----------------------------------------------------

        if delay > 0:

            print(
                f"⏳ Auto Reply: "
                f"{chat_id} → "
                f"{delay} min."
            )

            await asyncio.sleep(
                delay * 60
            )

        # ----------------------------------------------------
        # CHECK SETTINGS AGAIN
        # ----------------------------------------------------

        settings = await _load_settings()

        mode = settings.get(
            "mode",
            "off",
        )

        if mode == "off":

            return

        # ----------------------------------------------------
        # CHECK CURRENT MESSAGE
        # ----------------------------------------------------

        if not _is_current_message(
            chat_id,
            sender_id,
            text,
        ):

            return

        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        print(
            f"🧠 Generating Auto Reply "
            f"for {chat_id}"
        )

        answer = await _generate_answer(
            sender_id,
            text,
        )

        if not answer:

            return

        answer = str(
            answer
        ).strip()

        if not answer:

            return

        # ----------------------------------------------------
        # ASK MODE
        # ----------------------------------------------------

        if mode == "ask":

            reply_id = await create_pending_reply(
                chat_id=chat_id,
                user_id=sender_id,
                incoming_message_id=0,
                suggested_text=answer,
            )

            await _send_approval_request(
                reply_id,
                chat_id,
                sender_id,
                text,
                answer,
            )

            print(
                f"❓ Approval requested: "
                f"{reply_id}"
            )

            return

        # ----------------------------------------------------
        # AUTO MODE
        # ----------------------------------------------------

        if mode == "auto":

            from telethon_client import (
                client,
            )

            await client.send_message(
                chat_id,
                answer,
            )

            _total_replies += 1

            print()
            print(
                "🤖 AUTO REPLY SENT"
            )
            print(
                f"💬 Chat: {chat_id}"
            )
            print(
                f"📝 Reply: {answer}"
            )

    except asyncio.CancelledError:

        raise

    except Exception as e:

        _total_errors += 1

        print(
            "❌ AutoReply worker error: "
            f"{type(e).__name__}: {e}"
        )

    finally:

        task = _pending_tasks.get(
            chat_id
        )

        if task is current_task:

            _pending_tasks.pop(
                chat_id,
                None,
            )

            _pending_messages.pop(
                chat_id,
                None,
            )


# ============================================================
# INCOMING MESSAGE
# ============================================================

async def register_incoming(
    chat_id: int,
    sender_id: int,
    text: str,
    message_id: int = 0,
):

    global _total_scheduled

    if not chat_id:
        return

    if not sender_id:
        return

    if not text:
        return

    text = str(
        text
    ).strip()

    if not text:
        return

    # --------------------------------------------------------
    # SETTINGS
    # --------------------------------------------------------

    settings = await _load_settings()

    mode = settings.get(
        "mode",
        "off",
    )

    delay = settings.get(
        "delay_minutes",
        0,
    )

    # --------------------------------------------------------
    # OFF
    # --------------------------------------------------------

    if mode == "off":

        return

    # --------------------------------------------------------
    # CANCEL OLD TASK
    # --------------------------------------------------------

    _cancel_task(
        chat_id
    )

    # --------------------------------------------------------
    # SAVE MESSAGE
    # --------------------------------------------------------

    _pending_messages[
        chat_id
    ] = {
        "sender_id": sender_id,
        "text": text,
        "message_id": message_id,
        "created_at": time.time(),
        "delay": delay,
    }

    # --------------------------------------------------------
    # CREATE TASK
    # --------------------------------------------------------

    task = asyncio.create_task(
        _worker(
            chat_id,
            sender_id,
            text,
            delay,
        )
    )

    _pending_tasks[
        chat_id
    ] = task

    _total_scheduled += 1

    print()
    print(
        "⚡ AUTO REPLY SCHEDULED"
    )
    print(
        f"💬 Chat: {chat_id}"
    )
    print(
        f"👤 Sender: {sender_id}"
    )
    print(
        f"🎛 Mode: {mode}"
    )
    print(
        f"⏱ Delay: {delay} min."
    )


# ============================================================
# PENDING REPLY
# ============================================================

async def get_pending_reply(
    reply_id,
):

    try:

        return await db_get_pending_reply(
            reply_id
        )

    except Exception as e:

        print(
            "❌ Get pending reply error: "
            f"{type(e).__name__}: {e}"
        )

        return None


# ============================================================
# EDIT PENDING REPLY
# ============================================================

async def set_pending_reply_text(
    reply_id,
    text,
):

    try:

        return await update_pending_reply(
            reply_id,
            suggested_text=text,
        )

    except Exception as e:

        print(
            "❌ Update pending reply error: "
            f"{type(e).__name__}: {e}"
        )

        return False


# ============================================================
# APPROVE
# ============================================================

async def approve_pending_reply(
    reply_id,
):

    global _total_replies
    global _total_errors

    pending = await get_pending_reply(
        reply_id
    )

    if not pending:

        return False

    if pending.get(
        "status"
    ) != "pending":

        return False

    try:

        from telethon_client import (
            client,
        )

        chat_id = pending.get(
            "chat_id"
        )

        answer = pending.get(
            "suggested_text",
            "",
        )

        if not chat_id:

            return False

        if not answer:

            return False

        await client.send_message(
            chat_id,
            answer,
        )

        await update_pending_reply(
            reply_id,
            status="approved",
        )

        _total_replies += 1

        print(
            f"✅ Approved reply sent: "
            f"{chat_id}"
        )

        return True

    except Exception as e:

        _total_errors += 1

        print(
            "❌ Approve reply error: "
            f"{type(e).__name__}: {e}"
        )

        return False


# ============================================================
# DENY
# ============================================================

async def deny_pending_reply(
    reply_id,
):

    pending = await get_pending_reply(
        reply_id
    )

    if not pending:

        return False

    if pending.get(
        "status"
    ) != "pending":

        return False

    try:

        await update_pending_reply(
            reply_id,
            status="denied",
        )

        return True

    except Exception as e:

        print(
            "❌ Deny reply error: "
            f"{type(e).__name__}: {e}"
        )

        return False


# ============================================================
# REMAINING
# ============================================================

def get_remaining(
    chat_id: int,
):

    data = _pending_messages.get(
        chat_id
    )

    task = _pending_tasks.get(
        chat_id
    )

    if not data:

        return 0

    if task is None:

        return 0

    if task.done():

        return 0

    delay = data.get(
        "delay",
        0,
    )

    elapsed = (
        time.time()
        - data.get(
            "created_at",
            time.time(),
        )
    )

    remaining = (
        delay * 60
    ) - elapsed

    return max(
        0,
        int(remaining),
    )


# ============================================================
# RESET STATISTICS
# ============================================================

def reset_autoreply_statistics():

    global _total_scheduled
    global _total_replies
    global _total_cancelled
    global _total_errors

    _total_scheduled = 0
    _total_replies = 0
    _total_cancelled = 0
    _total_errors = 0

    print(
        "📊 Auto Reply statistics reset."
    )