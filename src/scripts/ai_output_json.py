from pathlib import Path
import json
import os
from ollama import Client

from src.backend.models import ExtractedData, ProcessingError


scripts_dir = Path(__file__).resolve().parent
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


def _read_prompt(name):
    path = scripts_dir / "prompts" / name
    try:
        prompt = path.read_text(encoding="utf-8")
        print(f"Промпт загружен: {path.name} ({len(prompt)} символов)", flush=True)
        return prompt
    except OSError as exc:
        raise ProcessingError(f"Failed to read AI prompt {name}: {exc}") from exc


def _get_client():
    print(f"Подключение к Ollama: {OLLAMA_HOST}", flush=True)
    client = Client(host=OLLAMA_HOST)
    print("Получение списка моделей Ollama...", flush=True)
    local_models = client.list()
    models = getattr(local_models, "models", None)
    if models is None:
        models = local_models.get("models", [])
    models_list = [
        getattr(model, "model", None) or model.get("model", "")
        for model in models
    ]
    if not any(MODEL_NAME in m for m in models_list):
        print(
            f"Модель {MODEL_NAME} не найдена локально. Запускается загрузка.",
            flush=True,
        )
        client.pull(MODEL_NAME)
        print(f"Модель {MODEL_NAME} загружена.", flush=True)
    else:
        print(f"Модель {MODEL_NAME} готова к работе.", flush=True)
    return client


def process_text_with_ai(email_content, output_path, attachment_names=()):
    if not email_content.strip():
        raise ProcessingError("No email text was provided to the AI stage")

    preprocessing_prompt = _read_prompt("prompt_for_preprocessing.txt")
    json_prompt = _read_prompt("prompt_for_json.txt")
    filenames = "\n".join(attachment_names) or "(нет вложений)"
    client = _get_client()

    try:
        print(
            f"Первичная AI-обработка текста ({len(email_content)} символов)...",
            flush=True,
        )
        response = client.generate(
            model=MODEL_NAME,
            prompt=(
                f"{preprocessing_prompt}\n\n"
                f"ИМЕНА ВЛОЖЕНИЙ:\n{filenames}\n\n"
            ),
            options={"temperature": 0.2, "thinking": False, "num_ctx": 40960},
        )
        preliminary_text = _response_text(response)
        print(
            f"Первичная AI-обработка завершена "
            f"({len(preliminary_text)} символов результата).",
            flush=True,
        )
        print("Преобразование результата AI в строгий JSON...", flush=True)
        json_response = client.generate(
            model=MODEL_NAME,
            prompt=f"{json_prompt}\n{preliminary_text}",
            format="json",
            options={"temperature": 0.2, "thinking": False, "num_ctx": 40960},
        )
    except Exception as exc:
        raise ProcessingError(f"AI processing failed: {exc}") from exc

    json_text = _response_text(json_response)
    print(f"Ответ JSON получен ({len(json_text)} символов).", flush=True)
    extracted = ExtractedData.from_json(json_text)
    print("JSON успешно проверен по схеме.", flush=True)
    output_path.write_text(
        json.dumps(extracted.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Результат AI сохранен: {output_path}", flush=True)
    return extracted


def process_raw_email_text(email_content, output_path):
    return process_text_with_ai(email_content, output_path)


def _response_text(response):
    text = getattr(response, "response", None)
    if text is None:
        text = response["response"]
    if not isinstance(text, str):
        raise ProcessingError("Ollama returned an invalid response")
    return text
