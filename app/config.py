"""Application configuration, loaded from environment / ``.env``.

Only *bootstrap* and *infrastructure* values live here (DB location, admin
credentials, cookie secret, and the first-run Telegram token). Everything the
bot says or checks at runtime — texts, channel, questions, feature toggles —
lives in the database so it can be edited from the dashboard without a redeploy.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = the directory that contains this ``app`` package.
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram bootstrap (seeded into the DB on first run) ---
    bot_token: str = "PASTE_YOUR_BOT_TOKEN_HERE"
    channel_id: int = 0
    channel_link: str = "https://t.me/"

    # --- Dashboard auth ---
    admin_username: str = "admin"
    admin_password: str = "change-me-please"
    secret_key: str = "change-this-to-a-long-random-string"

    # --- Infrastructure ---
    database_url: str = "sqlite:///./data/app.db"
    upload_dir: str = "./data/uploads"

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()


settings = get_settings()
