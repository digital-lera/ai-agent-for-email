from __future__ import annotations

import email
import imaplib
import json
import re
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path
from typing import Any

from src.backend.directum_rules import (
    apply_email_rules,
    forward_original_email,
    load_directum_rules,
)
from src.backend.models import MessageContext, ProcessingError
from src.backend.progress import emit_progress, progress_store, schedule_progress_reset
from src.backend.statistics import emit_statistics, increment_and_emit
from src.scripts.send_error_task import create_error_task


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
JOBS_DIR = SCRIPTS_DIR / "jobs"
LOGIN_PATH = SCRIPTS_DIR / "login.json"
DEFAULT_IMAP_SERVER = "ukexch.uktaif.ru"
DEFAULT_PROCESSED_FOLDER = "AI"
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024


def decode_mime_header(header_value: str | None) -> str:
    if not header_value:
        return ""
    try:
        return str(make_header(decode_header(header_value))).strip()
    except (LookupError, UnicodeDecodeError):
        return header_value


def decode_filename(file_name: str | None) -> str:
    decoded = decode_mime_header(file_name) or "attachment"
    decoded = decoded.replace("\x00", "").replace("\\", "/")
    safe_name = Path(decoded).name.strip().strip(".")
    safe_name = re.sub(r"[\r\n\t]", "_", safe_name)
    return safe_name or "attachment"


def read_email_text(message: Message) -> str:
    plain_parts = []
    html_parts = []
    for part in message.walk():
        if part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        text = _decode_part(part)
        if content_type == "text/plain":
            plain_parts.append(text)
        else:
            html_parts.append(text)
    return "\n\n".join(plain_parts or html_parts).strip()


def load_config(path: Path = LOGIN_PATH) -> dict[str, Any]:
    last_error = None
    for encoding in ("utf-8", "windows-1251", "latin-1"):
        try:
            with path.open("r", encoding=encoding) as login_file:
                config = json.load(login_file)
            if not isinstance(config, dict):
                raise ProcessingError("login.json must contain a JSON object")
            return config
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = exc
        except OSError as exc:
            raise ProcessingError(f"Failed to read {path}: {exc}") from exc
    raise ProcessingError(f"Failed to decode {path}: {last_error}")


def check_email(socketio) -> int:
    """Poll the inbox once and return the number of messages inspected."""
    print("\nПроверка почты...", flush=True)
    config = load_config()
    emit_statistics(socketio)
    imap = None
    try:
        imap = _connect(config)
        print("Поиск непрочитанных сообщений...", flush=True)
        status, data = imap.search(None, "UNSEEN")
        _require_ok(status, "search inbox")
        message_ids = data[0].split() if data and data[0] else []
        print(f"Найдено непрочитанных сообщений: {len(message_ids)}", flush=True)

        for message_number in message_ids:
            try:
                _process_one_message(imap, message_number, socketio, config)
            except Exception as exc:
                print(
                    f"Ошибка обработки IMAP-сообщения {message_number!r}: {exc}",
                    flush=True,
                )
                socketio.emit("error", {"message": str(exc)})
                _mark_for_manual_processing(imap, message_number)
        return len(message_ids)
    finally:
        if imap is not None:
            _safe_logout(imap)


def _connect(config: dict[str, Any]):
    try:
        username = str(config["username"])
        password = str(config["email-password"])
    except KeyError as exc:
        raise ProcessingError(f"Missing email configuration field: {exc}") from exc

    server = str(config.get("imap_server", DEFAULT_IMAP_SERVER))
    imap = imaplib.IMAP4_SSL(server)
    status, response = imap.login(username, password)
    _require_ok(status, "login", response)
    status, response = imap.select("INBOX")
    _require_ok(status, "select inbox", response)
    return imap


def _process_one_message(
    imap,
    message_number: bytes,
    socketio,
    config: dict[str, Any],
) -> None:
    print(f"\nПолучение сообщения IMAP #{message_number.decode()}...", flush=True)
    status, msg_data = imap.fetch(message_number, "(BODY.PEEK[])")
    _require_ok(status, "fetch message", msg_data)
    if not msg_data or not isinstance(msg_data[0], tuple):
        raise ProcessingError("IMAP returned an empty message")

    message = email.message_from_bytes(msg_data[0][1])
    subject = decode_mime_header(message.get("subject"))
    sender = decode_mime_header(message.get("from"))
    print(f"Найдено письмо: {subject}", flush=True)
    print(f"Отправитель: {sender}", flush=True)
    context = MessageContext(
        subject=subject,
        sender=sender,
        message_id=message.get("message-id", message_number.decode()),
        root_dir=JOBS_DIR,
        raw_message=msg_data[0][1],
        raw_text=read_email_text(message),
    )
    context.prepare()
    print(f"Рабочая директория создана: {context.work_dir}", flush=True)
    print(
        f"Текст тела письма: {len(context.raw_text)} символов.",
        flush=True,
    )

    socketio.emit("reset")
    progress_store.start_email(
        job_id=context.job_id,
        subject=subject,
        sender=sender,
    )
    emit_progress(socketio)
    socketio.emit("new_email", {"subject": subject, "sender": sender})
    statistics_tracked = False
    try:
        rules = load_directum_rules(config)
        email_decision = apply_email_rules(
            rules,
            sender=sender,
            subject=subject,
            body=context.raw_text,
            attachment_names=_message_attachment_names(message),
        )
        if email_decision.forward_to:
            forward_original_email(
                original_message=context.raw_message,
                original_subject=context.subject,
                sender=context.sender,
                recipients=email_decision.forward_to,
                config=config,
            )
        if email_decision.skip_directum:
            if email_decision.forward_to:
                print(
                    "Письмо перенаправлено по правилу: "
                    f"{', '.join(email_decision.forward_to)}",
                    flush=True,
                )
            print(
                "Письмо не передается в AI/Directum по правилу: "
                f"{email_decision.reason}",
                flush=True,
            )
            progress_store.update(
                {
                    "status": "completed",
                    "chain": {
                        "stage": "Маршрутизация письма",
                        "status": "Завершено",
                        "log": email_decision.reason,
                    },
                    "message": "Письмо обработано правилом маршрутизации",
                }
            )
            emit_progress(socketio)
            increment_and_emit(socketio, "received", context.message_id)
            increment_and_emit(socketio, "successful", context.message_id)
            statistics_tracked = True
        else:
            if email_decision.forward_to:
                print(
                    "Письмо перенаправлено по правилу: "
                    f"{', '.join(email_decision.forward_to)}",
                    flush=True,
                )
            _save_attachments(message, context, socketio, config)
            if not context.pdf_attachments:
                print(
                    "PDF-вложения не найдены. Письмо не передается в pipeline.",
                    flush=True,
                )
                progress_store.update(
                    {
                        "status": "error",
                        "chain": {
                            "stage": "Проверка вложений",
                            "status": "Ошибка",
                            "log": "PDF-вложения не найдены. Требуется ручная обработка.",
                        },
                        "message": "Письмо помечено для ручной обработки",
                    }
                )
                emit_progress(socketio)
                _mark_for_manual_processing(imap, message_number)
                schedule_progress_reset(socketio, context.job_id)
                return

            increment_and_emit(socketio, "received", context.message_id)
            statistics_tracked = True
            from src.backend.process_message import run_chain

            result = run_chain(socketio, context, config)
            if not result.success:
                raise ProcessingError(result.error or "Processing pipeline failed")
            if statistics_tracked:
                outcome = "partial" if result.review_task_created else "successful"
                increment_and_emit(socketio, outcome, context.message_id)
    except Exception as exc:
        print(f"Письмо обработать не удалось: {exc}", flush=True)
        progress_store.update(
            {
                "status": "error",
                "chain": {
                    "stage": "Ошибка обработки",
                    "status": "Ошибка",
                    "log": str(exc),
                },
                "message": "Ошибка! Дополнительную информацию можно найти в консоли или логах",
            }
        )
        emit_progress(socketio)
        socketio.emit("error", {"message": str(exc)})
        _mark_for_manual_processing(imap, message_number)
        print("Письмо помечено флагом для ручной обработки.", flush=True)
        try:
            print("Создание задачи об ошибке в Directum RX...", flush=True)
            create_error_task(subject, sender, str(exc), config)
            print("Задача об ошибке создана.", flush=True)
            if statistics_tracked:
                increment_and_emit(socketio, "manual", context.message_id)
        except Exception as task_exc:
            print(f"Не удалось создать задачу об ошибке: {task_exc}", flush=True)
            socketio.emit(
                "error",
                {"message": f"{exc}; error task also failed: {task_exc}"},
            )
        finally:
            schedule_progress_reset(socketio, context.job_id)
    else:
        print("Все этапы успешны. Перемещение письма в обработанные.", flush=True)
        try:
            _move_to_processed(imap, message_number, config)
        except Exception as move_exc:
            print(
                f"Обработка завершена, но письмо не перемещено: {move_exc}",
                flush=True,
            )
            socketio.emit("error", {"message": str(move_exc)})
            _mark_for_manual_processing(imap, message_number)
            progress_store.update(
                {
                    "status": "error",
                    "chain": {
                        "stage": "Перемещение письма",
                        "status": "Ошибка",
                        "log": str(move_exc),
                    },
                    "message": "Обработка завершена, но письмо не перемещено",
                }
            )
            emit_progress(socketio)
            schedule_progress_reset(socketio, context.job_id)
        else:
            schedule_progress_reset(socketio, context.job_id)
    finally:
        print(f"Очистка рабочей директории: {context.work_dir}", flush=True)
        context.cleanup()


def _save_attachments(
    message: Message,
    context: MessageContext,
    socketio,
    config: dict[str, Any],
) -> None:
    max_bytes = int(config.get("max_attachment_bytes", MAX_ATTACHMENT_BYTES))
    used_names: set[str] = set()

    for part in message.walk():
        original_name = part.get_filename()
        if not original_name:
            continue
        payload = part.get_payload(decode=True) or b""
        if not payload:
            raise ProcessingError(
                f"Attachment {decode_filename(original_name)} is empty"
            )
        if len(payload) > max_bytes:
            raise ProcessingError(
                f"Attachment {decode_filename(original_name)} exceeds "
                f"the {max_bytes}-byte limit"
            )

        safe_name = _unique_name(decode_filename(original_name), used_names)
        path = context.work_dir / safe_name
        path.write_bytes(payload)
        print(
            f"Вложение сохранено: {safe_name} ({len(payload)} байт)",
            flush=True,
        )
        context.attachments.append(path)
        if path.suffix.lower() == ".pdf":
            context.pdf_attachments.append(path)
            print(f"Вложение добавлено в очередь OCR: {safe_name}", flush=True)
        elif part.get_content_maintype() == "text":
            attachment_text = _decode_part(part).strip()
            if attachment_text:
                context.raw_text = "\n\n".join(
                    filter(None, (context.raw_text, attachment_text))
                )
                print(
                    f"Текстовое вложение добавлено к письму: {safe_name}",
                    flush=True,
                )
        socketio.emit("filename_recognized", safe_name)
        progress_store.update({"filename": safe_name})
        emit_progress(socketio)

    print(
        f"Всего вложений: {len(context.attachments)}, "
        f"PDF: {len(context.pdf_attachments)}",
        flush=True,
    )


def _message_attachment_names(message: Message) -> tuple[str, ...]:
    return tuple(
        decode_filename(file_name)
        for part in message.walk()
        if (file_name := part.get_filename())
    )


def _move_to_processed(imap, message_number: bytes, config: dict[str, Any]) -> None:
    folder = str(config.get("processed_folder", DEFAULT_PROCESSED_FOLDER))
    print(f"Проверка папки IMAP '{folder}'...", flush=True)
    create_status, _ = imap.create(folder)
    if create_status not in {"OK", "NO"}:
        raise ProcessingError(f"Could not create or access IMAP folder {folder}")

    status, response = imap.copy(message_number, folder)
    _require_ok(status, f"copy message to {folder}", response)
    status, response = imap.store(message_number, "+FLAGS", r"(\Deleted)")
    _require_ok(status, "mark source message deleted", response)
    status, response = imap.expunge()
    _require_ok(status, "expunge source message", response)
    print(
        f"Письмо {message_number.decode()} перемещено в '{folder}'.",
        flush=True,
    )


def _mark_for_manual_processing(imap, message_number: bytes) -> None:
    try:
        imap.store(message_number, "+FLAGS", r"(\Flagged \Seen)")
    except imaplib.IMAP4.error:
        pass


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    encodings = [
        part.get_content_charset(),
        "utf-8",
        "windows-1251",
        "latin-1",
    ]
    for encoding in filter(None, encodings):
        try:
            return payload.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return payload.decode("utf-8", errors="replace")


def _unique_name(name: str, used_names: set[str]) -> str:
    candidate = name
    stem = Path(name).stem
    suffix = Path(name).suffix
    index = 2
    while candidate.casefold() in used_names:
        candidate = f"{stem}-{index}{suffix}"
        index += 1
    used_names.add(candidate.casefold())
    return candidate


def _require_ok(status: str, action: str, response=None) -> None:
    if status != "OK":
        raise ProcessingError(f"IMAP failed to {action}: {response}")


def _safe_logout(imap) -> None:
    try:
        imap.close()
    except (imaplib.IMAP4.error, OSError):
        pass
    try:
        imap.logout()
    except (imaplib.IMAP4.error, OSError):
        pass
