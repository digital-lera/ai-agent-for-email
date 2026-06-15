from datetime import datetime, timedelta
from typing import Any
import warnings

from src.scripts.directum import DirectumClient


warnings.filterwarnings("ignore", message="Unverified HTTPS request")


def create_error_task(
    subject: str,
    sender: str,
    reason: str,
    config: dict[str, Any],
) -> int:
    print(
        f"Подготовка задачи об ошибке: subject={subject!r}, sender={sender!r}",
        flush=True,
    )
    client = DirectumClient.from_config(config)

    task_text = (
        "Письмо не было обработано и требует ручной обработки.\n"
        f"Отправитель: {sender or 'неизвестен'}\n"
        f"Тема: {subject or 'не указана'}\n"
        f"Причина: {reason}"
    )
    print("Создание и отправка задачи об ошибке в Directum...", flush=True)
    task_id = client.create_and_start_simple_task(
        {
            "assignmentType": "Assignment",
            "deadline": (
                datetime.now().astimezone() + timedelta(days=1)
            ).isoformat(),
            "subject": "Входящее письмо не было обработано агентом.",
            "importance": "Normal",
            "text": task_text,
            "performerIds": [client.performer_id],
            "observerIds": [client.performer_id],
            "documentIds": [],
        }
    )
    print(
        f"Задача об ошибке создана и отправлена, id={task_id}.",
        flush=True,
    )
    return task_id
