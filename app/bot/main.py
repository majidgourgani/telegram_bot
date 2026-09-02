"""Bot entry point.

Reads the token from the database (seeded from the environment on first run),
so the dashboard is the single source of truth for configuration. Changing the
token requires restarting this process.

A background task also delivers dashboard-queued broadcasts.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden, RetryAfter, TelegramError
from telegram.ext import Application, ApplicationBuilder

from app.bot.handlers import build_conversation
from app.database import init_db
from app.services import broadcast, content

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ~20 messages/second stays comfortably under Telegram's broadcast limits.
_SEND_INTERVAL = 0.05
_POLL_INTERVAL = 8  # seconds between checks for a queued broadcast
_PROGRESS_EVERY = 25  # persist progress every N sends


async def _deliver_broadcast(bot, job: dict) -> None:
    recipients = broadcast.resolve_recipient_ids(job["target"], job.get("recipient_ids"))
    broadcast.set_total(job["id"], len(recipients))

    markup = None
    if job.get("add_button"):
        link = content.get_setting("channel_link", "")
        label = job.get("button_text") or "عضویت در کانال"
        if link:
            markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton(label, url=link)]]
            )

    sent = failed = 0
    logger.info("Broadcast #%s: sending to %s recipients", job["id"], len(recipients))

    for index, user_id in enumerate(recipients, start=1):
        try:
            await bot.send_message(chat_id=user_id, text=job["message"], reply_markup=markup)
            sent += 1
        except RetryAfter as exc:  # flood control — wait then retry once
            await asyncio.sleep(float(exc.retry_after) + 1)
            try:
                await bot.send_message(chat_id=user_id, text=job["message"], reply_markup=markup)
                sent += 1
            except TelegramError:
                failed += 1
        except Forbidden:  # user blocked the bot or deactivated their account
            failed += 1
            broadcast.mark_blocked(user_id)
        except TelegramError:
            failed += 1

        if index % _PROGRESS_EVERY == 0:
            broadcast.update_progress(job["id"], sent, failed)
        await asyncio.sleep(_SEND_INTERVAL)

    broadcast.finish(job["id"], sent, failed)
    logger.info("Broadcast #%s done: %s sent, %s failed", job["id"], sent, failed)


async def _broadcast_worker(application: Application) -> None:
    bot = application.bot
    while True:
        try:
            job = broadcast.fetch_next_pending()
            if job is not None:
                await _deliver_broadcast(bot, job)
                continue  # immediately check for another queued job
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — worker must never die
            logger.exception("Broadcast worker error")
        await asyncio.sleep(_POLL_INTERVAL)


async def _post_init(application: Application) -> None:
    # Recover any broadcast interrupted by a previous shutdown, then start worker.
    broadcast.requeue_stuck_sending()
    application.create_task(_broadcast_worker(application))


def run() -> None:
    # Ensure schema + seed data exist before we read the token.
    init_db()

    token = content.get_setting("bot_token", "")
    if not token or token == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError(
            "Bot token is not configured. Set BOT_TOKEN in .env (first run) "
            "or update it on the dashboard Settings page, then restart the bot."
        )

    application = ApplicationBuilder().token(token).post_init(_post_init).build()
    application.add_handler(build_conversation())

    logger.info("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    run()
