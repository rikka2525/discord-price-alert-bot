"""Small SQLite repository for price alerts."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Alert:
    id: int
    guild_id: int
    channel_id: int
    user_id: int
    coin_id: str
    target_price: float
    direction: str


class AlertRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        parent = Path(self.database_path).parent
        parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    coin_id TEXT NOT NULL,
                    target_price REAL NOT NULL CHECK (target_price > 0),
                    direction TEXT NOT NULL CHECK (direction IN ('above', 'below')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (guild_id, user_id, coin_id, target_price, direction)
                )
                """
            )

    def add_alert(
        self,
        *,
        guild_id: int,
        channel_id: int,
        user_id: int,
        coin_id: str,
        target_price: float,
        direction: str,
    ) -> int:
        if target_price <= 0:
            raise ValueError("target_price must be greater than zero")
        if direction not in {"above", "below"}:
            raise ValueError("direction must be 'above' or 'below'")

        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO alerts
                    (guild_id, channel_id, user_id, coin_id, target_price, direction)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (guild_id, channel_id, user_id, coin_id.lower(), target_price, direction),
            )
            return int(cursor.lastrowid)

    def list_alerts(self, *, guild_id: int, user_id: int | None = None) -> list[Alert]:
        query = "SELECT id, guild_id, channel_id, user_id, coin_id, target_price, direction FROM alerts WHERE guild_id = ?"
        params: list[int] = [guild_id]
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY id"
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(query, params).fetchall()
        return [Alert(**dict(row)) for row in rows]

    def delete_alert(self, *, alert_id: int, guild_id: int, user_id: int) -> bool:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "DELETE FROM alerts WHERE id = ? AND guild_id = ? AND user_id = ?",
                (alert_id, guild_id, user_id),
            )
            return cursor.rowcount > 0

    def delete_triggered(self, alert_id: int) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))

    def all_alerts(self) -> list[Alert]:
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                "SELECT id, guild_id, channel_id, user_id, coin_id, target_price, direction FROM alerts ORDER BY id"
            ).fetchall()
        return [Alert(**dict(row)) for row in rows]
