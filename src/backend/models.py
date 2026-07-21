from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


DATE_FORMAT = "%d.%m.%Y"
NUMBER_PATTERN = re.compile(r"^[0-9-]*$")
INN_PATTERN = re.compile(r"^(?:[0-9]{10}|[0-9]{12})$")
PERSON_PATTERN = re.compile(r"^[А-ЯЁA-Z][А-ЯЁа-яёA-Za-z'-]* [А-ЯЁA-Z]$")


class ProcessingError(RuntimeError):
    """Raised when an email cannot be processed safely."""


class ValidationError(ProcessingError):
    """Raised when extracted data does not match the Directum contract."""


@dataclass
class MessageContext:
    subject: str
    sender: str
    message_id: str
    root_dir: Path
    raw_message: bytes = b""
    raw_text: str = ""
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    attachments: list[Path] = field(default_factory=list)
    pdf_attachments: list[Path] = field(default_factory=list)

    @property
    def work_dir(self) -> Path:
        return self.root_dir / self.job_id

    @property
    def extracted_text_path(self) -> Path:
        return self.work_dir / "email.txt"

    @property
    def processed_data_path(self) -> Path:
        return self.work_dir / "processed_data.json"

    def prepare(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=False)

    def cleanup(self) -> None:
        shutil.rmtree(self.work_dir, ignore_errors=True)


@dataclass(frozen=True)
class ExtractedData:
    content: str
    correspondent: str
    inn: str
    date_from: str
    number: str
    signed_by: str
    recipient: str

    @classmethod
    def from_mapping(cls, value: Any) -> "ExtractedData":
        if not isinstance(value, dict):
            raise ValidationError("AI output must be a JSON object")

        content = str(value.get("content", "") or "").strip()
        correspondent = str(value.get("correspondent", "") or "").strip()
        inn = _normalize_inn(value.get("inn", ""))
        date_from = str(value.get("dateFrom", "") or "").strip()
        number = str(value.get("number", "") or "").strip()
        signed_by = str(value.get("signedBy", "") or "").strip()
        recipient = str(value.get("recipient", "") or "").strip()

        if not content:
            raise ValidationError("Агент не смог выделить краткое содержание письма")
        if date_from:
            try:
                datetime.strptime(date_from, DATE_FORMAT)
            except ValueError as exc:
                raise ValidationError(
                    f"Дата письма должна быть в формате DD.MM.YYYY: {date_from}"
                ) from exc
        if inn and not INN_PATTERN.match(inn):
            inn = ""

        return cls(
            content=content,
            correspondent=correspondent,
            inn=inn,
            date_from=date_from,
            number=number,
            signed_by=signed_by,
            recipient=recipient,
        )

    @classmethod
    def from_json(cls, raw: str) -> "ExtractedData":
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return cls.from_mapping(json.loads(cleaned))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"AI output is not valid JSON: {exc}") from exc

    def to_dict(self) -> dict[str, str]:
        return {
            "content": self.content,
            "correspondent": self.correspondent,
            "inn": self.inn,
            "dateFrom": self.date_from,
            "number": self.number,
            "signedBy": self.signed_by,
            "recipient": self.recipient,
        }


def _normalize_inn(value: Any) -> str:
    return re.sub(r"[\s-]+", "", str(value or "")).strip()


@dataclass(frozen=True)
class PipelineResult:
    success: bool
    document_id: int | None = None
    review_task_created: bool = False
    error: str | None = None
    skipped_directum: bool = False
    forwarded_to_recipient: bool = False


@dataclass(frozen=True)
class DirectumResult:
    document_id: int | None
    review_task_created: bool
    skipped_directum: bool = False
    forwarded_to_recipient: bool = False
