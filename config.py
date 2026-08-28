import os

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    try:
        return float(value)
    except ValueError:
        return default


# ============================================================
# TELEGRAM
# ============================================================

TG_API_ID = _get_int(
    "TG_API_ID",
    0,
)

TG_API_HASH = os.getenv(
    "TG_API_HASH",
    "",
).strip()

SESSION_NAME = os.getenv(
    "SESSION_NAME",
    "jarvis_session",
).strip()


# ============================================================
# BOT
# ============================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "",
).strip()


# ============================================================
# OWNER
# ============================================================

OWNER_ID = _get_int(
    "OWNER_ID",
    0,
)


# ============================================================
# AI
# ============================================================

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY",
    "",
).strip()

AI_MODEL = os.getenv(
    "AI_MODEL",
    "qwen/qwen3.8-27b",
).strip()

AI_MAX_TOKENS = _get_int(
    "AI_MAX_TOKENS",
    1000,
)

AI_TEMPERATURE = _get_float(
    "AI_TEMPERATURE",
    0.7,
)

MAX_MEMORY_MESSAGES = _get_int(
    "MAX_MEMORY_MESSAGES",
    40,
)


# ============================================================
# DATABASE
# ============================================================

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "jarvis.db",
).strip()


# ============================================================
# AUTO REPLY
# ============================================================

AUTO_REPLY_ENABLED = _get_bool(
    "AUTO_REPLY_ENABLED",
    True,
)

# 30 минут по умолчанию
AUTO_REPLY_DELAY = _get_int(
    "AUTO_REPLY_DELAY",
    1800,
)

AUTO_REPLY_MIN_TEXT_LENGTH = _get_int(
    "AUTO_REPLY_MIN_TEXT_LENGTH",
    1,
)


# ============================================================
# SECURITY
# ============================================================

SECURITY_ENABLED = _get_bool(
    "SECURITY_ENABLED",
    True,
)


# ------------------------------------------------------------
# Security modes
#
# strict   -> максимально строгий
# balanced -> обычный рекомендуемый режим
# safe     -> осторожный, меньше блокировок
# ------------------------------------------------------------

SECURITY_MODE = os.getenv(
    "SECURITY_MODE",
    "balanced",
).strip().lower()

if SECURITY_MODE not in {
    "strict",
    "balanced",
    "safe",
}:
    SECURITY_MODE = "balanced"


# ============================================================
# SPAM
# ============================================================

SPAM_THRESHOLD = _get_int(
    "SPAM_THRESHOLD",
    70,
)

SPAM_WINDOW = _get_int(
    "SPAM_WINDOW",
    60,
)

MAX_TRACKED_MESSAGES = _get_int(
    "MAX_TRACKED_MESSAGES",
    100,
)


# ============================================================
# SCAM
# ============================================================

SCAM_THRESHOLD = _get_int(
    "SCAM_THRESHOLD",
    70,
)


# ============================================================
# DUPLICATES
# ============================================================

DUPLICATE_WINDOW = _get_int(
    "DUPLICATE_WINDOW",
    120,
)


# ============================================================
# SECURITY ACTIONS
# ============================================================

SECURITY_AUTO_BLOCK = _get_bool(
    "SECURITY_AUTO_BLOCK",
    True,
)

SECURITY_WARN_OWNER = _get_bool(
    "SECURITY_WARN_OWNER",
    True,
)


# ============================================================
# MONITOR BOT
# ============================================================

MONITOR_ENABLED = _get_bool(
    "MONITOR_ENABLED",
    True,
)

MONITOR_LOG_MESSAGES = _get_bool(
    "MONITOR_LOG_MESSAGES",
    True,
)

MONITOR_LOG_SECURITY = _get_bool(
    "MONITOR_LOG_SECURITY",
    True,
)


# ============================================================
# AGRO MODE
# ============================================================

AGRO_MODE_ENABLED = _get_bool(
    "AGRO_MODE_ENABLED",
    False,
)

AGRO_MODE_DURATION = _get_int(
    "AGRO_MODE_DURATION",
    1800,
)


# ============================================================
# CHAT / MESSAGE LIMITS
# ============================================================

MAX_MESSAGE_LENGTH = _get_int(
    "MAX_MESSAGE_LENGTH",
    4000,
)

MAX_CONTEXT_MESSAGES = _get_int(
    "MAX_CONTEXT_MESSAGES",
    20,
)


# ============================================================
# DEBUG
# ============================================================

DEBUG = _get_bool(
    "DEBUG",
    False,
)

# ============================================================
# MESSAGE CACHE
# ============================================================

MAX_MESSAGE_CACHE = 5000


# ============================================================
# VALIDATION
# ============================================================

def validate_config():
    """
    Проверяет основные настройки JARVIS.
    Возвращает список ошибок.
    """

    errors = []

    if TG_API_ID <= 0:
        errors.append(
            "TG_API_ID не задан или некорректный."
        )

    if not TG_API_HASH:
        errors.append(
            "TG_API_HASH не задан."
        )

    if not BOT_TOKEN:
        errors.append(
            "BOT_TOKEN не задан."
        )

    if OWNER_ID <= 0:
        errors.append(
            "OWNER_ID не задан или некорректный."
        )

    if not GROQ_API_KEY:
        errors.append(
            "GROQ_API_KEY не задан."
        )

    if AUTO_REPLY_DELAY < 0:
        errors.append(
            "AUTO_REPLY_DELAY не может быть отрицательным."
        )

    if SPAM_THRESHOLD < 1 or SPAM_THRESHOLD > 100:
        errors.append(
            "SPAM_THRESHOLD должен быть от 1 до 100."
        )

    if SCAM_THRESHOLD < 1 or SCAM_THRESHOLD > 100:
        errors.append(
            "SCAM_THRESHOLD должен быть от 1 до 100."
        )

    if SPAM_WINDOW <= 0:
        errors.append(
            "SPAM_WINDOW должен быть больше 0."
        )

    if DUPLICATE_WINDOW <= 0:
        errors.append(
            "DUPLICATE_WINDOW должен быть больше 0."
        )

    return errors


# ============================================================
# STARTUP INFO
# ============================================================

def print_config():
    """
    Безопасно выводит конфигурацию.
    Секретные ключи не показываются.
    """

    print()
    print("=" * 60)
    print("⚙️ JARVIS CONFIG")
    print("=" * 60)

    print(
        f"📱 Telegram API: "
        f"{'OK' if TG_API_ID and TG_API_HASH else 'MISSING'}"
    )

    print(
        f"🤖 Bot Token: "
        f"{'OK' if BOT_TOKEN else 'MISSING'}"
    )

    print(
        f"👤 Owner ID: "
        f"{OWNER_ID}"
    )

    print(
        f"🧠 AI Model: "
        f"{AI_MODEL}"
    )

    print(
        f"💾 Database: "
        f"{DATABASE_PATH}"
    )

    print(
        f"⚡ Auto Reply: "
        f"{'ON' if AUTO_REPLY_ENABLED else 'OFF'}"
    )

    print(
        f"⏱️ Auto Reply Delay: "
        f"{AUTO_REPLY_DELAY} sec"
    )

    print(
        f"🛡️ Security: "
        f"{'ON' if SECURITY_ENABLED else 'OFF'}"
    )

    print(
        f"🔐 Security Mode: "
        f"{SECURITY_MODE}"
    )

    print(
        f"🚫 Auto Block: "
        f"{'ON' if SECURITY_AUTO_BLOCK else 'OFF'}"
    )

    print(
        f"🔥 Agro Mode: "
        f"{'ON' if AGRO_MODE_ENABLED else 'OFF'}"
    )

    print(
        f"🐛 Debug: "
        f"{'ON' if DEBUG else 'OFF'}"
    )

    print("=" * 60)
    print()


# ============================================================
# IMPORT VALIDATION
# ============================================================

_CONFIG_ERRORS = validate_config()

if _CONFIG_ERRORS:

    print()
    print("⚠️ CONFIGURATION WARNINGS:")

    for error in _CONFIG_ERRORS:
        print(f"   • {error}")

    print()
