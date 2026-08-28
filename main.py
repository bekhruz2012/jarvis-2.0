import asyncio

from config import (
    validate_config,
    OWNER_ID,
)

from database import (
    init_database,
    close_database,
)

from monitor_bot import (
    start_monitor_bot,
)

from telethon_client import (
    start_telegram,
    stop_telegram,
    set_monitor_bot,
)

from autoreply import (
    cancel_all_autoreplies,
)


# ============================================================
# MAIN
# ============================================================

async def main():

    print()
    print("=" * 60)
    print("🤖 JARVIS 2.0 STARTING")
    print("=" * 60)

    # --------------------------------------------------------
    # CONFIG
    # --------------------------------------------------------

    validate_config()

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    await init_database()

    monitor_application = None

    try:

        # ----------------------------------------------------
        # TELEGRAM
        # ----------------------------------------------------

        me = await start_telegram()

        # ----------------------------------------------------
        # MONITOR BOT
        # ----------------------------------------------------

        monitor_application = (
            await start_monitor_bot(
                owner_id=OWNER_ID
            )
        )

        set_monitor_bot(
            monitor_application.bot
        )

        # ----------------------------------------------------
        # ONLINE
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("🟢 JARVIS 2.0 ONLINE")
        print("=" * 60)
        print()

        print(
            f"👤 Account: {me.first_name}"
        )

        print(
            f"🆔 ID: {me.id}"
        )

        print()

        print(
            "🧠 AI: ONLINE"
        )

        print(
            "🛡️ Anti-Spam: 24/7"
        )

        print(
            "🎣 Anti-Scam: 24/7"
        )

        print(
            "🗑️ Deleted messages: ON"
        )

        print(
            "✏️ Edited messages: ON"
        )

        print(
            "📨 Auto Reply: 30 minutes"
        )

        print(
            "🔥 Agro Mode: maximum 30 minutes"
        )

        print()

        print(
            "Press Ctrl+C to stop."
        )

        print()

        await asyncio.Event().wait()

    except KeyboardInterrupt:

        print(
            "🛑 Keyboard interrupt."
        )

    finally:

        print()
        print(
            "🛑 Stopping JARVIS..."
        )

        # ----------------------------------------------------
        # AUTOREPLY
        # ----------------------------------------------------

        try:

            await cancel_all_autoreplies()

        except Exception as e:

            print(
                f"⚠️ AutoReply shutdown error: {e}"
            )

        # ----------------------------------------------------
        # MONITOR BOT
        # ----------------------------------------------------

        if monitor_application:

            try:

                if monitor_application.updater:

                    await (
                        monitor_application
                        .updater
                        .stop()
                    )

                await (
                    monitor_application
                    .stop()
                )

                await (
                    monitor_application
                    .shutdown()
                )

            except Exception as e:

                print(
                    f"⚠️ Monitor shutdown error: {e}"
                )

        # ----------------------------------------------------
        # TELEGRAM
        # ----------------------------------------------------

        try:

            await stop_telegram()

        except Exception as e:

            print(
                f"⚠️ Telegram shutdown error: {e}"
            )

        # ----------------------------------------------------
        # DATABASE
        # ----------------------------------------------------

        try:

            await close_database()

        except Exception as e:

            print(
                f"⚠️ Database shutdown error: {e}"
            )

        print(
            "🔴 JARVIS OFFLINE"
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "🛑 JARVIS stopped."
        )