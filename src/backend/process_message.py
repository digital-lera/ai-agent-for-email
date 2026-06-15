from src.backend.models import MessageContext, PipelineResult, ProcessingError


def run_chain(socketio, context: MessageContext, config: dict) -> PipelineResult:
    stages = (
        ("Получение текста документа", "text_parse", _extract_text),
        ("Выделение необходимых данных", "ai_data_recognition", _extract_data),
        ("Создание входящего письма в Directum RX", "directum_api", _create_document),
    )
    state = {"context": context, "config": config}

    for name, event_prefix, stage in stages:
        status = {"stage": name, "status": "В процессе", "log": ""}
        socketio.emit("chain_update", status)
        socketio.emit(f"{event_prefix}_started", True)

        try:
            stage(state)
        except Exception as exc:
            message = f"{name}: {exc}"
            socketio.emit(
                "chain_update",
                {"stage": name, "status": "Ошибка", "log": message},
            )
            socketio.emit("error", {"message": message})
            return PipelineResult(success=False, error=message)

        socketio.emit(
            "chain_update",
            {"stage": name, "status": "Завершено", "log": f"Процесс завершен - {name}"},
        )
        socketio.emit(f"{event_prefix}_finished", True)
        if event_prefix == "ai_data_recognition":
            socketio.emit(
                "json_data_received",
                state["extracted_data"].to_dict(),
            )

    document_id = state["document_id"]
    socketio.emit("chain_complete", {"document_id": document_id})
    return PipelineResult(success=True, document_id=document_id)


def _extract_text(state):
    context = state["context"]
    text_parts = [context.raw_text] if context.raw_text.strip() else []
    if context.pdf_attachments:
        from src.scripts.pdf_parse import pdf_parse

        pdf_output = context.work_dir / "ocr.txt"
        pdf_parse(context.pdf_attachments, pdf_output)
        text_parts.append(pdf_output.read_text(encoding="utf-8"))
    if not text_parts:
        raise ProcessingError("The email contains no readable body or PDF text")
    context.extracted_text_path.write_text(
        "\n\n".join(text_parts),
        encoding="utf-8",
    )


def _extract_data(state):
    from src.scripts.ai_output_json import process_text_with_ai

    context = state["context"]
    content = context.extracted_text_path.read_text(encoding="utf-8")
    state["extracted_data"] = process_text_with_ai(
        content,
        context.processed_data_path,
        [path.name for path in context.attachments],
    )


def _create_document(state):
    from src.scripts.directum import DirectumClient

    client = DirectumClient.from_config(state["config"])
    state["document_id"] = client.create_incoming_letter(
        state["extracted_data"],
        state["context"].pdf_attachments,
    )
