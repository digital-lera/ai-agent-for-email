# Конфигурация

## Локальный `login.json`

Создайте локальный файл `src/scripts/login.json`. Он зависит от конкретного
развертывания и не должен содержать общие тестовые учетные данные.

```json
{
  "username": "email-service-account",
  "email-password": "mail-password",
  "directum-username": "directum-service-account",
  "password": "directum-password",
  "odataurl": "https://directum.example/odata",
  "performer_id": 123,
  "imap_server": "ukexch.uktaif.ru",
  "processed_folder": "AI",
  "request_timeout": 30,
  "max_attachment_bytes": 52428800,
  "ocr_gpu": true,
  "ocr_workers": 0,
  "ocr_confidence": 0.5,
  "ocr_dpi": 200,
  "ocr_heartbeat_seconds": 15,
  "ocr_model_storage_dir": "/root/.EasyOCR/model",
  "directum_rules_path": "src/scripts/directum_rules.json",
  "smtp_server": "smtp.example",
  "smtp_port": 587,
  "smtp_use_tls": true
}
```

## Разделение учетных данных

- IMAP-почта использует `username` и `email-password`.
- Directum RX использует `directum-username` и `password`.
- SMTP-пересылка по умолчанию использует `username` и `email-password`.
- SMTP-пересылку можно переопределить через `smtp_username`,
  `smtp_password` и `forward_from`.

Разделение сделано специально: учетная запись почтового ящика и учетная запись
Directum могут быть разными пользователями.

## Переменные окружения

- `SOCKETIO_CORS_ORIGINS`: настройка CORS для Socket.IO.
- `OLLAMA_MODEL`: модель Ollama. По умолчанию `qwen3:8b`.
- `OLLAMA_HOST`: адрес Ollama. По умолчанию `http://localhost:11434`.
- `OCR_GPU`: переопределяет `ocr_gpu`.
- `OCR_CUDA_DEVICE`: индекс CUDA-устройства для OCR. По умолчанию `0`.
- `OCR_MODEL_STORAGE_DIR`: директория кэша моделей EasyOCR. По умолчанию
  `/root/.EasyOCR/model`.
- `STATISTICS_TIMEZONE`: часовой пояс дневной статистики. По умолчанию
  `Europe/Moscow`.

## Файл правил Directum

`directum_rules_path` указывает на JSON-файл бизнес-правил. Значение по
умолчанию — `src/scripts/directum_rules.json`.

Правила могут:

- останавливать AI/OCR/Directum на уровне входящего письма;
- останавливать обработку писем по исходному получателю из заголовков письма;
- пересылать исходное письмо;
- заменять ID Directum после поиска;
- принудительно выставлять ID Directum;
- пропускать создание документа Directum после поиска ID.

Схема правил описана в разделе [Интеграция с Directum](directum-integration.md).

## Внешние сервисы

- IMAP: `imaplib.IMAP4_SSL`.
- SMTP: `smtplib.SMTP`, обычно с STARTTLS.
- Ollama: локальный HTTP-сервис через Python-клиент `ollama`.
- Directum RX: OData endpoint из `odataurl`.
- OCR: `pdf2image`, EasyOCR, PyTorch и системный PDF renderer.
