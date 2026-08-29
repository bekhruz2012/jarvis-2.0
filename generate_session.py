import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import TG_API_ID, TG_API_HASH, SESSION_NAME


async def main():
    client = TelegramClient(
        SESSION_NAME,
        TG_API_ID,
        TG_API_HASH,
    )

    print("📱 Запускаем Telegram авторизацию...")

    await client.start()

    session_string = StringSession.save(
        client.session
    )

    print()
    print("=" * 70)
    print("✅ STRING SESSION СОЗДАНА")
    print("=" * 70)
    print()
    print(session_string)
    print()
    print("=" * 70)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())