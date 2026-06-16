from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
import warnings

import requests

from src.backend.directum_rules import (
    DirectumIds,
    apply_id_rules,
    forward_original_email,
    load_directum_rules,
)
from src.backend.models import DirectumResult, ExtractedData, MessageContext, ProcessingError


DEFAULT_TIMEOUT = 30
warnings.filterwarnings("ignore", message="Unverified HTTPS request")


def _person_key(value: str) -> str:
    parts = value.split()
    if len(parts) < 2:
        return ""
    return f"{parts[0]} {parts[1][0]}"


def find_fuzzy_id(
    items: list[dict[str, Any]],
    name_to_find: str,
    *,
    is_person: bool = False,
    threshold: int = 80,
) -> int:
    candidates = []
    for item in items:
        name = str(item.get("Name", ""))
        candidate = _person_key(name) if is_person else name
        if candidate:
            candidates.append((candidate, item.get("Id")))

    target = _person_key(name_to_find) if is_person else name_to_find
    scored = [
        (
            SequenceMatcher(
                None,
                target.casefold(),
                candidate.casefold(),
            ).ratio()
            * 100,
            candidate,
            item_id,
        )
        for candidate, item_id in candidates
    ]
    if not scored:
        return -1

    score, _, item_id = max(scored)
    return int(item_id) if score >= threshold else -1


@dataclass
class DirectumClient:
    base_url: str
    auth: tuple[str, str]
    performer_id: int
    timeout: int = DEFAULT_TIMEOUT
    config: dict[str, Any] = field(default_factory=dict)
    rules: list[dict[str, Any]] = field(default_factory=list)
    session: requests.Session = field(default_factory=requests.Session)
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.session.auth = self.auth
        self.session.verify = False

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "DirectumClient":
        try:
            return cls(
                base_url=str(config["odataurl"]),
                auth=(str(config["directum-username"]), str(config["password"])),
                performer_id=int(config["performer_id"]),
                timeout=int(config.get("request_timeout", DEFAULT_TIMEOUT)),
                config=config,
                rules=load_directum_rules(config),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProcessingError(f"Invalid Directum configuration: {exc}") from exc

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        print(f"Directum запрос: {method} {path}", flush=True)
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                verify=False,
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
            print(
                f"Directum ответ: {response.status_code} для {method} {path}",
                flush=True,
            )
            return response
        except requests.RequestException as exc:
            raise ProcessingError(
                f"Directum request failed: {method} {path}: {exc}"
            ) from exc

    @staticmethod
    def _extract_task_id(response: requests.Response) -> int:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProcessingError(
                "Directum did not return a simple task ID"
            ) from exc

        if isinstance(payload, bool):
            task_id = None
        elif isinstance(payload, int):
            task_id = payload
        elif isinstance(payload, str) and payload.strip().isdigit():
            task_id = int(payload.strip())
        elif isinstance(payload, dict):
            task_id = next(
                (
                    payload[key]
                    for key in ("Id", "id", "Value", "value")
                    if payload.get(key) is not None
                ),
                None,
            )
        else:
            task_id = None

        if isinstance(task_id, str) and task_id.strip().isdigit():
            task_id = int(task_id.strip())

        if not isinstance(task_id, int) or isinstance(task_id, bool):
            raise ProcessingError(
                f"Directum returned an invalid simple task ID: {payload!r}"
            )
        return task_id

    def create_and_start_simple_task(self, payload: dict[str, Any]) -> int:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Return": "representation",
        }
        response = self._request(
            "POST",
            "/Docflow/CreateSimpleTask",
            headers=headers,
            json=payload,
        )
        task_id = self._extract_task_id(response)
        print(
            f"Простая задача создана, id={task_id}. Отправка задачи...",
            flush=True,
        )

        self._request(
            "POST",
            "/Docflow/StartTask",
            headers=headers,
            json={"taskId": task_id},
        )
        print(f"Простая задача id={task_id} отправлена.", flush=True)
        return task_id

    def _lookup(self, entity: str, name: str, *, is_person: bool = False) -> int:
        if not name:
            print(f"Поиск {entity} пропущен: значение пустое.", flush=True)
            return -1

        print(f"Поиск в Directum {entity}: {name!r}", flush=True)
        first_character = name[0].replace("'", "''")
        response = self._request(
            "GET",
            f"/{entity}",
            params={
                "$filter": f"contains(Name,'{first_character}')",
                "$select": "Id,Name",
            },
        )
        payload = response.json()
        matched_id = find_fuzzy_id(
            payload.get("value", []),
            name,
            is_person=is_person,
        )
        print(
            f"Результат поиска {entity} для {name!r}: id={matched_id}",
            flush=True,
        )
        return matched_id

    def create_incoming_letter(
        self,
        data: ExtractedData,
        attachments: list[Path],
        context: MessageContext | None = None,
    ) -> DirectumResult:
        print("Поиск связанных сущностей Directum...", flush=True)
        signed_by_id = self._lookup("IContacts", data.signed_by, is_person=True)
        recipient_id = self._lookup("IEmployees", data.recipient, is_person=True)
        counterparty_id = self._lookup("ICounterparties", data.correspondent)
        ids = DirectumIds(
            signed_by_id=signed_by_id,
            recipient_id=recipient_id,
            counterparty_id=counterparty_id,
        )
        decision = apply_id_rules(self.rules, ids)
        if decision.matched_rules:
            print(
                "Правила Directum применены: "
                f"{', '.join(decision.matched_rules)}",
                flush=True,
            )
        ids = decision.apply_to_ids(ids)
        signed_by_id = ids.signed_by_id
        recipient_id = ids.recipient_id
        counterparty_id = ids.counterparty_id

        if decision.forward_to:
            if context is None:
                raise ProcessingError("Forwarding rule matched without message context")
            forward_original_email(
                original_message=context.raw_message,
                original_subject=context.subject,
                sender=context.sender,
                recipients=decision.forward_to,
                config=self.config,
            )
            print(
                f"Письмо перенаправлено по правилу: {', '.join(decision.forward_to)}",
                flush=True,
            )

        if decision.skip_directum:
            print(
                "Создание документа Directum пропущено по правилу: "
                f"{decision.reason}",
                flush=True,
            )
            return DirectumResult(
                document_id=None,
                review_task_created=False,
                skipped_directum=True,
            )

        if data.signed_by and signed_by_id < 1:
            self.errors.append(
                f"Контакт подписанта '{data.signed_by}' не найден."
            )
        if data.recipient and recipient_id < 1:
            self.errors.append(f"Адресат '{data.recipient}' не найден.")
        if data.correspondent and counterparty_id < 1:
            self.errors.append(
                f"Контрагент '{data.correspondent}' не найден."
            )

        payload: dict[str, Any] = {
            "Name": data.content,
            "Subject": data.content,
            "InNumber": data.number,
            "Note": (
                "ДОКУМЕНТ ОБРАБОТАН ИИ-АГЕНТОМ, "
                "данные необходимо перепроверить"
            ),
        }
        if data.date_from:
            payload["Dated"] = datetime.strptime(
                data.date_from, "%d.%m.%Y"
            ).date().isoformat()
        if counterparty_id > 0:
            payload["Correspondent@odata.bind"] = (
                f"{self.base_url}/ICounterparties({counterparty_id})"
            )
        if signed_by_id > 0:
            payload["SignedBy@odata.bind"] = (
                f"{self.base_url}/IContacts({signed_by_id})"
            )
        if recipient_id > 0:
            payload["Addressee@odata.bind"] = (
                f"{self.base_url}/IEmployees({recipient_id})"
            )

        response = self._request("POST", "/IIncomingLetters", json=payload)
        try:
            document_id = int(response.json()["Id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProcessingError(
                "Directum did not return an incoming letter ID"
            ) from exc

        print(f"Входящее письмо создано, id={document_id}", flush=True)
        print(f"Файлов для загрузки в Directum: {len(attachments)}", flush=True)
        for attachment in attachments:
            self._upload_attachment(document_id, attachment)

        review_task_created = bool(self.errors)
        if review_task_created:
            print(
                f"Обнаружены неточные данные: {len(self.errors)}. "
                "Создается задача на проверку.",
                flush=True,
            )
            self._create_review_task(document_id)
        print(f"Работа с Directum завершена, document_id={document_id}", flush=True)
        return DirectumResult(
            document_id=document_id,
            review_task_created=review_task_created,
        )

    def _upload_attachment(self, document_id: int, attachment: Path) -> None:
        print(f"Подготовка файла к загрузке: {attachment.name}", flush=True)
        try:
            content = attachment.read_bytes()
        except OSError as exc:
            raise ProcessingError(
                f"Failed to read attachment {attachment.name}: {exc}"
            ) from exc
        if not content:
            raise ProcessingError(f"Attachment {attachment.name} is empty")
        print(
            f"Размер загружаемого файла {attachment.name}: {len(content)} байт",
            flush=True,
        )

        version_response = self._request(
            "POST",
            f"/IIncomingLetters({document_id})/Versions",
            headers={"Return": "representation"},
            json={
                "Note": f"Файл, приложенный к письму: {attachment.name}",
                "AssociatedApplication": {"Id": 3},
            },
        )
        try:
            version_id = int(version_response.json()["Id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProcessingError(
                f"Directum did not return a version ID for {attachment.name}"
            ) from exc

        self._request(
            "PUT",
            (
                f"/IIncomingLetters({document_id})/Versions"
                f"({version_id})/Body/$value"
            ),
            headers={
                "Content-Type": "application/octet-stream",
                "Accept": "application/json",
            },
            data=content,
        )
        print(f"Файл {attachment.name} загружен в Directum.", flush=True)

    def _create_review_task(self, document_id: int) -> None:
        print(f"Создание задачи проверки для документа {document_id}.", flush=True)
        error_text = "\n".join(self.errors)
        task_id = self.create_and_start_simple_task(
            {
                "assignmentType": "Assignment",
                "deadline": (
                    datetime.now().astimezone() + timedelta(days=1)
                ).isoformat(),
                "subject": "Входящее письмо обработано с ошибкой.",
                "importance": "Normal",
                "text": (
                    "Некоторые данные письма требуют ручной проверки:\n"
                    f"{error_text}"
                ),
                "performerIds": [self.performer_id],
                "observerIds": [self.performer_id],
                "documentIds": [document_id],
            },
        )
        print(
            f"Задача проверки создана и отправлена, id={task_id}.",
            flush=True,
        )
