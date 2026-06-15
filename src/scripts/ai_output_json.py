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
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProcessingError(f"Failed to read AI prompt {name}: {exc}") from exc


def _get_client():
    client = Client(host=OLLAMA_HOST)
    local_models = client.list()
    models = getattr(local_models, "models", None)
    if models is None:
        models = local_models.get("models", [])
    models_list = [
        getattr(model, "model", None) or model.get("model", "")
        for model in models
    ]
    if not any(MODEL_NAME in m for m in models_list):
        print(f"Модель {MODEL_NAME} не найдена локально. Запускается загрузка.")
        client.pull(MODEL_NAME)
    return client


def process_text_with_ai(email_content, output_path, attachment_names=()):
    if not email_content.strip():
        raise ProcessingError("No email text was provided to the AI stage")

    preprocessing_prompt = _read_prompt("prompt_for_preprocessing.txt")
    json_prompt = _read_prompt("prompt_for_json.txt")
    filenames = "\n".join(attachment_names)
    client = _get_client()

    try:
        response = client.generate(
            model=MODEL_NAME,
            prompt=f"{preprocessing_prompt}\n\n{filenames}\n{email_content}",
            options={"temperature": 0.2, "thinking": False, "num_ctx": 40960},
        )
        json_response = client.generate(
            model=MODEL_NAME,
            prompt=f"{json_prompt}\n{_response_text(response)}",
            format="json",
            options={"temperature": 0.2, "thinking": False, "num_ctx": 40960},
        )
    except Exception as exc:
        raise ProcessingError(f"AI processing failed: {exc}") from exc

    extracted = ExtractedData.from_json(_response_text(json_response))
    output_path.write_text(
        json.dumps(extracted.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
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
