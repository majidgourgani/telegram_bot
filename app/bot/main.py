"""Bot entry point.

Reads the token from the database (seeded from the environment on first run),
so the dashboard is the single source of truth for configuration. Changing the
token requires restarting this process.
"""

from __future__ import annotations

import logging

from telegram.ext import ApplicationBuilder

from app.bot.handlers import build_conversation
from app.database import init_db
from app.services import content

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def run() -> None:
    # Ensure schema + seed data exist before we read the token.
    init_db()

    token = content.get_setting("bot_token", "")
    if not token or token == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError(
            "Bot token is not configured. Set BOT_TOKEN in .env (first run) "
            "or update it on the dashboard Settings page, then restart the bot."
        )

    application = ApplicationBuilder().token(token).build()
    application.add_handler(build_conversation())

    logger.info("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    run()
