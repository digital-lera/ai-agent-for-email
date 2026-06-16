from src.backend.models import MessageContext, PipelineResult, ProcessingError
from src.backend.progress import emit_progress, progress_store


def run_chain(socketio, context: MessageContext, config: dict) -> PipelineResult:
    print(
        f"Запущена обработка письма: subject={context.subject!r}, "
        f"sender={context.sender!r}, job_id={context.job_id}",
        flush=True,
    )
    stages = (
        ("Получение текста документа", "text_parse", _extract_text),
        ("Выделение необходимых данных", "ai_data_recognition", _extract_data),
        ("Создание входящего письма в Directum RX", "directum_api", _create_document),
    )
    state = {"context": context, "config": config}

    for name, event_prefix, stage in stages:
        print(f"\nТекущая операция: {name}", flush=True)
        status = {"stage": name, "status": "В процессе", "log": ""}
        progress_store.update(
            {
                "status": "running",
                "chain": status,
                "stages": {event_prefix: "in-process"},
                "message": f"В процессе: {name}",
            }
        )
        emit_progress(socketio)
        socketio.emit("chain_update", status)
        socketio.emit(f"{event_prefix}_started", True)

        try:
            stage(state)
        except Exception as exc:
            message = f"{name}: {exc}"
            print(f"Ошибка этапа: {message}", flush=True)
            error_status = {"stage": name, "status": "Ошибка", "log": message}
            progress_store.update(
                {
                    "status": "error",
                    "chain": error_status,
                    "stages": {event_prefix: "error"},
                    "message": "Ошибка! Дополнительную информацию можно найти в консоли или логах",
                }
            )
            emit_progress(socketio)
            socketio.emit(
                "chain_update",
                error_status,
            )
            socketio.emit("error", {"message": message})
            return PipelineResult(success=False, error=message)

        completed_status = {
            "stage": name,
            "status": "Завершено",
            "log": f"Процесс завершен - {name}",
        }
        progress_store.update(
            {
                "chain": completed_status,
                "stages": {event_prefix: "completed"},
                "message": f"Процесс завершен: {name}",
            }
        )
        emit_progress(socketio)
        socketio.emit(
            "chain_update",
            completed_status,
        )
        socketio.emit(f"{event_prefix}_finished", True)
        print(f"Процесс завершен: {name}", flush=True)
        if event_prefix == "ai_data_recognition":
            progress_store.update({"data": state["extracted_data"].to_dict()})
            emit_progress(socketio)
            socketio.emit(
                "json_data_received",
                state["extracted_data"].to_dict(),
            )

    directum_result = state["directum_result"]
    document_id = directum_result.document_id
    print(
        f"Обработка письма полностью завершена. Directum document_id={document_id}",
        flush=True,
    )
    progress_store.update(
        {
            "status": "completed",
            "message": "Обработка завершена",
        }
    )
    emit_progress(socketio)
    socketio.emit("chain_complete", {"document_id": document_id})
    return PipelineResult(
        success=True,
        document_id=document_id,
        review_task_created=directum_result.review_task_created,
        skipped_directum=directum_result.skipped_directum,
    )


def _extract_text(state):
    context = state["context"]
    text_parts = [context.raw_text] if context.raw_text.strip() else []
    if context.pdf_attachments:
        from src.scripts.pdf_parse import pdf_parse

        pdf_output = context.work_dir / "ocr.txt"
        print(
            f"Найдено PDF-вложений для OCR: {len(context.pdf_attachments)}",
            flush=True,
        )
        pdf_parse(context.pdf_attachments, pdf_output, state["config"])
        text_parts.append(pdf_output.read_text(encoding="utf-8"))
    if not text_parts:
        raise ProcessingError("The email contains no readable body or PDF text")
    context.extracted_text_path.write_text(
        "\n\n".join(text_parts),
        encoding="utf-8",
    )
    print(
        f"Объединенный текст сохранен: {context.extracted_text_path} "
        f"({context.extracted_text_path.stat().st_size} байт)",
        flush=True,
    )


def _extract_data(state):
    from src.scripts.ai_output_json import process_text_with_ai

    context = state["context"]
    content = context.extracted_text_path.read_text(encoding="utf-8")
    print(
        f"Передача текста в AI: {len(content)} символов, "
        f"вложений: {len(context.attachments)}",
        flush=True,
    )
    state["extracted_data"] = process_text_with_ai(
        content,
        context.processed_data_path,
        [path.name for path in context.attachments],
    )


def _create_document(state):
    from src.scripts.directum import DirectumClient

    client = DirectumClient.from_config(state["config"])
    print("Начинается создание документа в Directum RX.", flush=True)
    state["directum_result"] = client.create_incoming_letter(
        state["extracted_data"],
        state["context"].pdf_attachments,
        context=state["context"],
    )
