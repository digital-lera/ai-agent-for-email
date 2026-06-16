from __future__ import annotations

import json
import sqlite3
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.backend.statistics import DEFAULT_DATABASE_PATH


STAGE_KEYS = ("text_parse", "ai_data_recognition", "directum_api")
RESET_DELAY_SECONDS = 10


def _empty_snapshot() -> dict[str, Any]:
    return {
        "job_id": "",
        "status": "idle",
        "subject": "",
        "sender": "",
        "filename": "",
        "chain": {"stage": "", "status": "", "log": ""},
        "data": {
            "content": "",
            "correspondent": "",
            "dateFrom": "",
            "number": "",
            "signedBy": "",
            "recipient": "",
        },
        "stages": {
            "text_parse": "out-of-service",
            "ai_data_recognition": "out-of-service",
            "directum_api": "out-of-service",
        },
        "message": "Новых писем нет.",
        "updated_at": time.time(),
    }


@dataclass
class ProgressStore:
    database_path: Path = DEFAULT_DATABASE_PATH

    def __post_init__(self) -> None:
        self.database_path = Path(self.database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def get(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM processing_progress WHERE id = 1"
            ).fetchone()
        if row is None:
            return _empty_snapshot()
        try:
            payload = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            return _empty_snapshot()
        return _merge_snapshot(payload)

    def reset(self, *, job_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            current = self.get()
            if job_id is not None and current.get("job_id") != job_id:
                return current
            snapshot = _empty_snapshot()
            self._save(snapshot)
            return deepcopy(snapshot)

    def start_email(self, *, job_id: str, subject: str, sender: str) -> dict[str, Any]:
        snapshot = _empty_snapshot()
        snapshot.update(
            {
                "job_id": job_id,
                "status": "running",
                "subject": subject,
                "sender": sender,
                "message": f"Получено новое письмо!\nТема: {subject}\nОтправитель: {sender}",
                "updated_at": time.time(),
            }
        )
        return self.update(snapshot)

    def update(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            snapshot = self.get()
            _deep_update(snapshot, updates)
            snapshot["updated_at"] = time.time()
            self._save(snapshot)
            return deepcopy(snapshot)

    def set_stage(self, stage: str, status: str) -> dict[str, Any]:
        if stage not in STAGE_KEYS:
            return self.get()
        return self.update({"stages": {stage: status}})

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_progress (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL
                )
                """
            )

    def _save(self, snapshot: dict[str, Any]) -> None:
        payload = json.dumps(snapshot, ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO processing_progress (id, payload)
                VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (payload,),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path, timeout=30)


def emit_progress(socketio, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    current = snapshot or progress_store.get()
    socketio.emit("progress_update", current)
    return current


def schedule_progress_reset(socketio, job_id: str | None) -> None:
    def reset_later() -> None:
        time.sleep(RESET_DELAY_SECONDS)
        snapshot = progress_store.reset(job_id=job_id)
        socketio.emit("reset", snapshot)
        socketio.emit("progress_update", snapshot)

    start_background_task = getattr(socketio, "start_background_task", None)
    if callable(start_background_task):
        start_background_task(reset_later)
    else:
        threading.Thread(target=reset_later, daemon=True).start()


def _merge_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = _empty_snapshot()
    _deep_update(snapshot, payload)
    return snapshot


def _deep_update(target: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


progress_store = ProgressStore()
