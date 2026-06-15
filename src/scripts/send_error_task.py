from datetime import datetime, timedelta
from typing import Any

import requests

from src.backend.models import ProcessingError


DEFAULT_TIMEOUT = 30


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def create_error_task(
    subject: str,
    sender: str,
    reason: str,
    config: dict[str, Any],
) -> None:
    print(
        f"Подготовка задачи об ошибке: subject={subject!r}, sender={sender!r}",
        flush=True,
    )
    try:
        base_url = str(config["odataurl"]).rstrip("/")
        auth = (str(config["username"]), str(config["password"]))
        performer_id = int(config["performer_id"])
        verify_tls = _as_bool(config.get("verify_tls", True))
        timeout = int(config.get("request_timeout", DEFAULT_TIMEOUT))
    except (KeyError, TypeError, ValueError) as exc:
        raise ProcessingError(
            f"Cannot create an error task with invalid configuration: {exc}"
        ) from exc

    task_text = (
        "Письмо не было обработано и требует ручной обработки.\n"
        f"Отправитель: {sender or 'неизвестен'}\n"
        f"Тема: {subject or 'не указана'}\n"
        f"Причина: {reason}"
    )
    try:
        print("Отправка задачи об ошибке в Directum...", flush=True)
        response = requests.post(
            f"{base_url}/Docflow/CreateSimpleTask",
            verify=verify_tls,
            timeout=timeout,
            auth=auth,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Return": "representation",
            },
            json={
                "assignmentType": "Assignment",
                "deadline": (
                    datetime.now().astimezone() + timedelta(days=1)
                ).isoformat(),
                "subject": "Входящее письмо не было обработано агентом.",
                "importance": "Normal",
                "text": task_text,
                "performerIds": [performer_id],
                "observerIds": [performer_id],
                "documentIds": [],
            },
        )
        response.raise_for_status()
        print(
            f"Задача об ошибке создана, HTTP {response.status_code}.",
            flush=True,
        )
    except requests.RequestException as exc:
        raise ProcessingError(f"Failed to create Directum error task: {exc}") from exc
