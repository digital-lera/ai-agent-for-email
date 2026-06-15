from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests

from src.backend.models import ExtractedData, ProcessingError


DEFAULT_TIMEOUT = 30


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
    verify_tls: bool = True
    timeout: int = DEFAULT_TIMEOUT
    session: requests.Session = field(default_factory=requests.Session)
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.session.auth = self.auth
        self.session.verify = self.verify_tls

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "DirectumClient":
        try:
            return cls(
                base_url=str(config["odataurl"]),
                auth=(str(config["username"]), str(config["password"])),
                performer_id=int(config["performer_id"]),
                verify_tls=_as_bool(config.get("verify_tls", True)),
                timeout=int(config.get("request_timeout", DEFAULT_TIMEOUT)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProcessingError(f"Invalid Directum configuration: {exc}") from exc

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        print(f"Directum запрос: {method} {path}", flush=True)
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
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
    ) -> int:
        print("Поиск связанных сущностей Directum...", flush=True)
        signed_by_id = self._lookup("IContacts", data.signed_by, is_person=True)
        recipient_id = self._lookup("IEmployees", data.recipient, is_person=True)
        counterparty_id = self._lookup("ICounterparties", data.correspondent)

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

        if self.errors:
            print(
                f"Обнаружены неточные данные: {len(self.errors)}. "
                "Создается задача на проверку.",
                flush=True,
            )
            self._create_review_task(document_id)
        print(f"Работа с Directum завершена, document_id={document_id}", flush=True)
        return document_id

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
        self._request(
            "POST",
            "/Docflow/CreateSimpleTask",
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
        print("Задача проверки создана.", flush=True)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}
