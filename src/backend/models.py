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
    date_from: str
    number: str
    signed_by: str
    recipient: str

    @classmethod
    def from_mapping(cls, value: Any) -> "ExtractedData":
        if not isinstance(value, dict):
            raise ValidationError("AI output must be a JSON object")

        required = {
            "content",
            "correspondent",
            "dateFrom",
            "number",
            "signedBy",
            "recipient",
        }

        fields = {key: value[key] for key in required}

        content = fields["content"].strip()
        correspondent = fields["correspondent"].strip()
        date_from = fields["dateFrom"].strip()
        number = fields["number"].strip()
        signed_by = fields["signedBy"].strip()
        recipient = fields["recipient"].strip()

        if not content:
            raise ValidationError("Агент не смог выделить краткое содержание письма")
        if date_from:
            try:
                datetime.strptime(date_from, DATE_FORMAT)
            except ValueError as exc:
                raise ValidationError(
                    f"Дата письма должна быть в формате DD.MM.YYYY: {date_from}"
                ) from exc

        return cls(
            content=content,
            correspondent=correspondent,
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
            "dateFrom": self.date_from,
            "number": self.number,
            "signedBy": self.signed_by,
            "recipient": self.recipient,
        }


@dataclass(frozen=True)
class PipelineResult:
    success: bool
    document_id: int | None = None
    review_task_created: bool = False
    error: str | None = None
    skipped_directum: bool = False


@dataclass(frozen=True)
class DirectumResult:
    document_id: int | None
    review_task_created: bool
    skipped_directum: bool = False
