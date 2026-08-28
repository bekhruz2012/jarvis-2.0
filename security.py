import re
import time
from collections import defaultdict, deque

from config import (
    SECURITY_ENABLED,
    SPAM_THRESHOLD,
    SCAM_THRESHOLD,
    SPAM_WINDOW,
    MAX_TRACKED_MESSAGES,
    DUPLICATE_WINDOW,
)

from database import increment_stat


# ============================================================
# STATE
# ============================================================

_user_messages = defaultdict(
    lambda: deque(maxlen=MAX_TRACKED_MESSAGES)
)

_duplicate_cache = defaultdict(
    lambda: deque(maxlen=MAX_TRACKED_MESSAGES)
)

_blocked_users = set()


# ============================================================
# KEYWORDS
# ============================================================

SCAM_KEYWORDS = [
    # English
    "give me your code",
    "send me your code",
    "verification code",
    "login code",
    "telegram code",
    "otp",
    "password",
    "account will be deleted",
    "account is locked",
    "account blocked",
    "verify your account",
    "verify account",
    "security alert",
    "security warning",
    "urgent",
    "immediately",
    "you won",
    "winner",
    "prize",
    "free money",
    "crypto giveaway",
    "investment",

    # Russian
    "пароль",
    "код подтверждения",
    "код из смс",
    "код из sms",
    "пришли код",
    "скинь код",
    "отправь код",
    "дай код",
    "подтверждение аккаунта",
    "подтверди аккаунт",
    "ваш аккаунт заблокирован",
    "ваш аккаунт будет удален",
    "аккаунт будет удалён",
    "срочно",
    "немедленно",
    "вы выиграли",
    "ты выиграл",
    "приз",
    "бесплатные деньги",
    "инвестиция",
    "инвестиции",
]


SPAM_KEYWORDS = [
    # English
    "buy now",
    "click here",
    "subscribe",
    "follow me",
    "free",
    "bonus",
    "sale",
    "discount",
    "promo",
    "promotion",
    "giveaway",
    "airdrop",

    # Russian
    "заработок",
    "заработай",
    "скидка",
    "бесплатно",
    "акция",
    "розыгрыш",
    "подпишись",
    "переходи",
    "жми сюда",
]


SUSPICIOUS_DOMAINS = [
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "is.gd",
    "cutt.ly",
    "rb.gy",
    "shorturl.at",
]


URGENCY_WORDS = [
    "urgent",
    "immediately",
    "срочно",
    "немедленно",
    "прямо сейчас",
    "сейчас же",
]


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):
    """
    Нормализует текст для анализа.
    """

    if not text:
        return ""

    try:
        text = str(text).lower().strip()
    except Exception:
        return ""

    # Убираем повторяющиеся пробелы
    text = re.sub(r"\s+", " ", text)

    return text


# ============================================================
# URL DETECTION
# ============================================================

_URL_PATTERN = re.compile(
    r"""
    (?:
        https?://
        |
        www\.
        |
        t\.me/
        |
        telegram\.me/
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def contains_url(text):
    """
    Возвращает True, если в тексте есть ссылка.
    """

    if not text:
        return False

    return bool(
        _URL_PATTERN.search(str(text))
    )


def count_urls(text):
    """
    Возвращает количество URL.
    """

    if not text:
        return 0

    return len(
        _URL_PATTERN.findall(str(text))
    )


# ============================================================
# SCAM SCORE
# ============================================================

def calculate_scam_score(text):
    """
    Анализирует сообщение на признаки scam/phishing.
    """

    normalized = normalize_text(text)

    if not normalized:
        return 0, []

    score = 0
    reasons = []

    # --------------------------------------------------------
    # Scam keywords
    # --------------------------------------------------------

    matched_keywords = [
        keyword
        for keyword in SCAM_KEYWORDS
        if keyword in normalized
    ]

    if matched_keywords:
        score += min(
            60,
            len(matched_keywords) * 25,
        )

        reasons.append(
            "обнаружены признаки попытки "
            "получения чувствительных данных"
        )

    # --------------------------------------------------------
    # URLs
    # --------------------------------------------------------

    url_count = count_urls(normalized)

    if url_count:
        score += min(
            25,
            url_count * 10,
        )

        reasons.append(
            "сообщение содержит ссылку"
        )

    # --------------------------------------------------------
    # Suspicious domains
    # --------------------------------------------------------

    suspicious_found = any(
        domain in normalized
        for domain in SUSPICIOUS_DOMAINS
    )

    if suspicious_found:
        score += 25

        reasons.append(
            "обнаружена подозрительная "
            "сокращённая ссылка"
        )

    # --------------------------------------------------------
    # Urgency
    # --------------------------------------------------------

    urgency_count = sum(
        1
        for word in URGENCY_WORDS
        if word in normalized
    )

    if urgency_count:
        score += min(
            20,
            urgency_count * 10,
        )

        reasons.append(
            "используется давление "
            "и срочность"
        )

    return min(100, score), reasons


# ============================================================
# SPAM SCORE
# ============================================================

def calculate_spam_score(user_id, text):
    """
    Анализирует частоту и характер сообщений пользователя.
    """

    normalized = normalize_text(text)

    if not user_id:
        return 0, []

    score = 0
    reasons = []
    now = time.time()

    history = _user_messages[user_id]

    # --------------------------------------------------------
    # Add current message
    # --------------------------------------------------------

    history.append(
        {
            "time": now,
            "text": normalized,
        }
    )

    # --------------------------------------------------------
    # Remove expired messages
    # --------------------------------------------------------

    while history:

        oldest = history[0]

        if (
            now - oldest["time"]
            <= SPAM_WINDOW
        ):
            break

        history.popleft()

    recent = list(history)

    # --------------------------------------------------------
    # Message flood
    # --------------------------------------------------------

    message_count = len(recent)

    if message_count >= 5:

        score += min(
            50,
            (message_count - 4) * 10,
        )

        reasons.append(
            "слишком много сообщений "
            f"за {SPAM_WINDOW} секунд"
        )

    # --------------------------------------------------------
    # Very short messages
    # --------------------------------------------------------

    if 0 < len(normalized) <= 3:

        score += 5

    # --------------------------------------------------------
    # Repeated messages
    # --------------------------------------------------------

    duplicate_count = sum(
        1
        for item in recent
        if item["text"] == normalized
    )

    if duplicate_count >= 3:

        score += 35

        reasons.append(
            "повторяющиеся одинаковые сообщения"
        )

    elif duplicate_count >= 2:

        score += 20

        reasons.append(
            "повтор сообщения"
        )

    # --------------------------------------------------------
    # Spam keywords
    # --------------------------------------------------------

    matched_keywords = [
        keyword
        for keyword in SPAM_KEYWORDS
        if keyword in normalized
    ]

    if matched_keywords:

        score += min(
            30,
            len(matched_keywords) * 10,
        )

        reasons.append(
            "обнаружены признаки спама"
        )

    # --------------------------------------------------------
    # Multiple links
    # --------------------------------------------------------

    url_count = count_urls(normalized)

    if url_count >= 2:

        score += 25

        reasons.append(
            "несколько ссылок в сообщении"
        )

    elif url_count == 1:

        score += 10

    # --------------------------------------------------------
    # Very long message
    # --------------------------------------------------------

    if len(normalized) >= 1000:

        score += 10

        reasons.append(
            "слишком длинное сообщение"
        )

    # --------------------------------------------------------
    # Excessive punctuation
    # --------------------------------------------------------

    if re.search(
        r"[!?]{4,}",
        normalized,
    ):

        score += 10

        reasons.append(
            "чрезмерное количество "
            "знаков пунктуации"
        )

    return min(100, score), reasons


# ============================================================
# DUPLICATE DETECTION
# ============================================================

def is_duplicate(user_id, text):
    """
    Проверяет, отправлял ли пользователь
    такое же сообщение недавно.
    """

    normalized = normalize_text(text)

    if not normalized or not user_id:
        return False

    now = time.time()

    cache = _duplicate_cache[user_id]

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    while cache:

        oldest = cache[0]

        if (
            now - oldest["time"]
            <= DUPLICATE_WINDOW
        ):
            break

        cache.popleft()

    # --------------------------------------------------------
    # Check
    # --------------------------------------------------------

    for item in cache:

        if item["text"] == normalized:
            return True

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    cache.append(
        {
            "time": now,
            "text": normalized,
        }
    )

    return False


# ============================================================
# ACTION DECISION
# ============================================================

def decide_action(
    spam_score,
    scam_score,
):
    """
    Определяет действие Security.
    """

    # Scam имеет приоритет.
    if scam_score >= SCAM_THRESHOLD:
        return "block"

    # Spam.
    if spam_score >= SPAM_THRESHOLD:
        return "block"

    # Warning при 70% от порога.
    if scam_score >= SCAM_THRESHOLD * 0.70:
        return "warn"

    if spam_score >= SPAM_THRESHOLD * 0.70:
        return "warn"

    return "allow"


# ============================================================
# MAIN ANALYZER
# ============================================================

async def analyze_message(
    user_id,
    chat_id,
    text,
):
    """
    Главный Security analyzer.

    Возвращает:

        action
        spam_score
        scam_score
        reason
        event_type
        duplicate
        user_id
        chat_id
    """

    # ========================================================
    # SECURITY DISABLED
    # ========================================================

    if not SECURITY_ENABLED:

        return {
            "action": "allow",
            "spam_score": 0,
            "scam_score": 0,
            "reason": "Security disabled",
            "event_type": "disabled",
            "duplicate": False,
            "user_id": user_id,
            "chat_id": chat_id,
        }

    text = text or ""

    # ========================================================
    # EMPTY MESSAGE
    # ========================================================

    if not text.strip():

        return {
            "action": "allow",
            "spam_score": 0,
            "scam_score": 0,
            "reason": "Empty message",
            "event_type": "normal",
            "duplicate": False,
            "user_id": user_id,
            "chat_id": chat_id,
        }

    # ========================================================
    # STATISTICS
    #
    # ВАЖНО:
    # security_checks увеличивается здесь ОДИН раз.
    # telethon_client.py больше не должен увеличивать
    # этот counter после analyze_message().
    # ========================================================

    try:

        await increment_stat(
            "security_checks"
        )

    except Exception as e:

        print(
            "⚠️ Security statistics error: "
            f"{type(e).__name__}: {e}"
        )

    # ========================================================
    # ALREADY BLOCKED
    # ========================================================

    if user_id in _blocked_users:

        return {
            "action": "blocked",
            "spam_score": 100,
            "scam_score": 100,
            "reason": "Пользователь уже заблокирован.",
            "event_type": "blocked",
            "duplicate": False,
            "user_id": user_id,
            "chat_id": chat_id,
        }

    # ========================================================
    # CALCULATE SCORES
    # ========================================================

    spam_score, spam_reasons = (
        calculate_spam_score(
            user_id,
            text,
        )
    )

    scam_score, scam_reasons = (
        calculate_scam_score(
            text
        )
    )

    # ========================================================
    # DUPLICATE
    # ========================================================

    duplicate = is_duplicate(
        user_id,
        text,
    )

    if duplicate:

        spam_score = min(
            100,
            spam_score + 20,
        )

        spam_reasons.append(
            "повторное сообщение"
        )

    # ========================================================
    # COMBINE REASONS
    # ========================================================

    reasons = []

    reasons.extend(
        spam_reasons
    )

    reasons.extend(
        scam_reasons
    )

    # Убираем дубликаты, сохраняя порядок.
    reasons = list(
        dict.fromkeys(
            reasons
        )
    )

    if reasons:

        reason = "; ".join(
            reasons
        )

    else:

        reason = (
            "Подозрительных признаков "
            "не обнаружено."
        )

    # ========================================================
    # ACTION
    # ========================================================

    action = decide_action(
        spam_score,
        scam_score,
    )

    # ========================================================
    # EVENT TYPE
    # ========================================================

    if action == "block":

        if scam_score >= SCAM_THRESHOLD:

            event_type = "scam"

        else:

            event_type = "spam"

    elif action == "warn":

        event_type = "warning"

    elif action == "blocked":

        event_type = "blocked"

    else:

        event_type = "normal"

    # ========================================================
    # MEMORY
    # ========================================================

    if action == "block":

        _blocked_users.add(
            user_id
        )

        try:

            await increment_stat(
                "security_blocks"
            )

        except Exception as e:

            print(
                "⚠️ Block statistics error: "
                f"{type(e).__name__}: {e}"
            )

    elif action == "warn":

        try:

            await increment_stat(
                "security_warnings"
            )

        except Exception as e:

            print(
                "⚠️ Warning statistics error: "
                f"{type(e).__name__}: {e}"
            )

    # ========================================================
    # RESULT
    # ========================================================

    result = {
        "action": action,

        "spam_score": int(
            spam_score
        ),

        "scam_score": int(
            scam_score
        ),

        "reason": reason,

        "event_type": event_type,

        "duplicate": duplicate,

        "user_id": user_id,

        "chat_id": chat_id,
    }

    # ========================================================
    # LOG
    # ========================================================

    print()
    print(
        "🛡️ SECURITY ANALYSIS"
    )

    print(
        f"👤 User: {user_id}"
    )

    print(
        f"💬 Chat: {chat_id}"
    )

    print(
        f"🛡️ Spam: {spam_score}/100"
    )

    print(
        f"🎣 Scam: {scam_score}/100"
    )

    print(
        f"⚙️ Action: {action}"
    )

    print(
        f"📌 Reason: {reason}"
    )

    return result


# ============================================================
# BLOCK MEMORY
# ============================================================

def remember_blocked_user(user_id):
    """
    Добавляет пользователя во внутренний Security block list.
    """

    if user_id:
        _blocked_users.add(
            user_id
        )


def forget_blocked_user(user_id):
    """
    Удаляет пользователя из внутреннего block list.
    """

    if user_id:
        _blocked_users.discard(
            user_id
        )


def is_user_blocked(user_id):
    """
    Проверяет внутренний Security block list.
    """

    return user_id in _blocked_users


# ============================================================
# SECURITY STATUS
# ============================================================

def get_security_status():
    """
    Возвращает состояние Security.
    """

    return {
        "enabled": SECURITY_ENABLED,

        "tracked_users": len(
            _user_messages
        ),

        "blocked_users": len(
            _blocked_users
        ),

        "spam_threshold": SPAM_THRESHOLD,

        "scam_threshold": SCAM_THRESHOLD,

        "spam_window": SPAM_WINDOW,

        "duplicate_window": DUPLICATE_WINDOW,

        "tracked_messages": sum(
            len(messages)
            for messages in _user_messages.values()
        ),

        "duplicate_cache_users": len(
            _duplicate_cache
        ),
    }


# ============================================================
# CLEAR USER HISTORY
# ============================================================

def clear_user_history(user_id):
    """
    Очищает историю Security конкретного пользователя.
    """

    _user_messages.pop(
        user_id,
        None,
    )

    _duplicate_cache.pop(
        user_id,
        None,
    )


# ============================================================
# CLEAR BLOCK
# ============================================================

def clear_block(user_id):
    """
    Снимает внутренний Security block
    и очищает историю пользователя.
    """

    _blocked_users.discard(
        user_id
    )

    clear_user_history(
        user_id
    )


# ============================================================
# CLEAR EVERYTHING
# ============================================================

def clear_security_memory():
    """
    Полностью очищает внутреннюю память Security.
    """

    _user_messages.clear()

    _duplicate_cache.clear()

    _blocked_users.clear()

    print(
        "🧹 Security memory cleared."
    )
