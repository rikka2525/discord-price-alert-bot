"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    discord_token: str
    check_interval_minutes: int
    database_path: str
    log_level: str


def load_settings(*, require_token: bool = True) -> Settings:
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if require_token and not token:
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and add your token."
        )

    try:
        interval = int(os.getenv("CHECK_INTERVAL_MINUTES", "5"))
    except ValueError as exc:
        raise RuntimeError("CHECK_INTERVAL_MINUTES must be an integer.") from exc
    if interval < 1:
        raise RuntimeError("CHECK_INTERVAL_MINUTES must be at least 1.")

    return Settings(
        discord_token=token,
        check_interval_minutes=interval,
        database_path=os.getenv("DATABASE_PATH", "alerts.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
