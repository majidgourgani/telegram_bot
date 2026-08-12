"""Financial-scan Telegram bot + web dashboard.

The package is split into three layers:

* ``app`` (this level) — shared foundations: config, database, ORM models,
  seed data and the service layer that both the bot and the web app use.
* ``app.bot`` — the Telegram bot (python-telegram-bot).
* ``app.web`` — the FastAPI admin dashboard.
"""

__all__ = ["__version__"]

__version__ = "1.0.0"
