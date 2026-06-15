from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime
import os
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_DATABASE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "statistics.sqlite3"
)
COUNTER_COLUMNS = {
    "received": "received",
    "successful": "successful",
    "partial": "partial",
    "manual": "manual",
}
COUNTER_GROUPS = {
    "received": "received",
    "successful": "outcome",
    "partial": "outcome",
    "manual": "outcome",
}
STATISTICS_TIMEZONE = ZoneInfo(
    os.getenv("STATISTICS_TIMEZONE", "Europe/Moscow")
)


@dataclass(frozen=True)
class DailyStatistics:
    day: str
    received: int
    successful: int
    partial: int
    manual: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "date": self.day,
            "received": self.received,
            "successful": self.successful,
            "partial": self.partial,
            "manual": self.manual,
        }


class StatisticsStore:
    def __init__(self, database_path: Path = DEFAULT_DATABASE_PATH):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def get_today(self) -> DailyStatistics:
        return self.get_day(_today())

    def get_day(self, day: date) -> DailyStatistics:
        day_value = day.isoformat()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT day, received, successful, partial, manual
                FROM daily_statistics
                WHERE day = ?
                """,
                (day_value,),
            ).fetchone()

        if row is None:
            return DailyStatistics(day_value, 0, 0, 0, 0)
        return DailyStatistics(*row)

    def increment(
        self,
        counter: str,
        *,
        message_id: str,
        day: date | None = None,
    ) -> DailyStatistics:
        column = COUNTER_COLUMNS.get(counter)
        if column is None:
            raise ValueError(f"Unknown statistics counter: {counter}")
        event_group = COUNTER_GROUPS[counter]

        target_day = day or _today()
        day_value = target_day.isoformat()
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO daily_statistics (
                        day, received, successful, partial, manual
                    ) VALUES (?, 0, 0, 0, 0)
                    ON CONFLICT(day) DO NOTHING
                    """,
                    (day_value,),
                )
                cursor = connection.execute(
                    """
                    INSERT INTO statistics_events_v2 (
                        day, message_id, event_group, counter
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(day, message_id, event_group) DO NOTHING
                    """,
                    (day_value, message_id, event_group, counter),
                )
                if cursor.rowcount:
                    connection.execute(
                        f"""
                        UPDATE daily_statistics
                        SET {column} = {column} + 1
                        WHERE day = ?
                        """,
                        (day_value,),
                    )
        return self.get_day(target_day)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_statistics (
                    day TEXT PRIMARY KEY,
                    received INTEGER NOT NULL DEFAULT 0,
                    successful INTEGER NOT NULL DEFAULT 0,
                    partial INTEGER NOT NULL DEFAULT 0,
                    manual INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS statistics_events_v2 (
                    day TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    event_group TEXT NOT NULL,
                    counter TEXT NOT NULL,
                    PRIMARY KEY (day, message_id, event_group)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path, timeout=30)


statistics_store = StatisticsStore()


def emit_statistics(socketio, snapshot: DailyStatistics | None = None) -> None:
    current = snapshot or statistics_store.get_today()
    socketio.emit("statistics_update", current.to_dict())


def increment_and_emit(
    socketio,
    counter: str,
    message_id: str,
) -> DailyStatistics:
    snapshot = statistics_store.increment(counter, message_id=message_id)
    print(
        "Статистика обновлена: "
        f"date={snapshot.day}, received={snapshot.received}, "
        f"successful={snapshot.successful}, partial={snapshot.partial}, "
        f"manual={snapshot.manual}",
        flush=True,
    )
    emit_statistics(socketio, snapshot)
    return snapshot


def _today() -> date:
    return datetime.now(STATISTICS_TIMEZONE).date()
