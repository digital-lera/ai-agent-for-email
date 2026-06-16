# TAIF-mail

*AI-инструмент для обработки корпоративной почты и выделения ключевых данных из
входящих писем*

**[v0.1.0 pre-release](https://github.com/digital-lera/ai-agent-for-email/releases/tag/0.1.0) опубликован.**

## Документация

Полная документация проекта находится в [`docs/`](docs/README.md). Там есть
описание архитектуры, конфигурации, правил Directum, тестов, сопровождения и
пользовательский справочник по маршрутам обработки писем.

## Конфигурация запуска

Создайте локальный файл `src/scripts/login.json`. Файл игнорируется Git и
должен содержать:

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

Все запросы к Directum RX используют `verify=False`, потому что API этого
развертывания требует отключенной проверки TLS-сертификата.

`ocr_gpu` по умолчанию равен `true`. Контейнер приложения настроен с NVIDIA GPU
reservation, а EasyOCR не должен незаметно переключаться на CPU. При запуске
OCR выводит версию PyTorch, CUDA runtime, доступность CUDA, имя GPU, VRAM,
compute capability и версию cuDNN. `OCR_CUDA_DEVICE` выбирает индекс GPU и по
умолчанию равен `0`.

Версия CUDA на хосте/драйвере и CUDA runtime внутри PyTorch не обязаны
совпадать по minor-версии. Драйвер NVIDIA должен поддерживать runtime,
показанный в `torch.version.cuda`. Во время обработки каждой страницы OCR
печатает heartbeat каждые `ocr_heartbeat_seconds`.

Модели EasyOCR хранятся в `ocr_model_storage_dir`. В Docker Compose директория
`/root/.EasyOCR` вынесена в named volume `easyocr`, поэтому detection и
recognition модели не скачиваются заново после пересоздания контейнера.

Каждое письмо обрабатывается в отдельной папке внутри `src/scripts/jobs`.
Письмо переносится в обработанную IMAP-папку только после успешного OCR,
валидации AI, создания документа Directum и загрузки всех вложений. Если
обработка падает, письмо помечается для ручной обработки и создается задача в
Directum.

## Правила обработки Directum

Правила, которые меняют или пропускают обработку Directum, находятся в
`src/scripts/directum_rules.json`. Это обычный JSON-файл, который можно
редактировать без изменения Python-кода.

Каждое правило содержит:

- `name`: понятное имя правила для логов;
- `enabled`: `false`, если правило нужно временно отключить;
- `when`: условие;
- `actions`: одно или несколько действий при совпадении условия.

Поддерживаемые условия:

- `sender_email`: точное совпадение email отправителя без учета регистра;
- `sender_contains`: текст содержится в полном заголовке `From`;
- `text_contains_any`: нечеткое совпадение по теме и тексту письма;
- `attachment_name_contains_any`: нечеткое совпадение по имени вложения без
  расширения;
- `signed_by_id`: ID контакта Directum после поиска;
- `recipient_id`: ID сотрудника Directum после поиска;
- `counterparty_id`: ID контрагента Directum после поиска;
- `any_id`: совпадение по signed-by, recipient или counterparty ID.

Поддерживаемые действия:

- `skip_directum`: не создавать входящее письмо в Directum. Для правил уровня
  письма это также останавливает AI/OCR;
- `replace_matched_id`: заменить тот ID, который совпал с условием;
- `set_signed_by_id`: принудительно выставить конкретный `SignedBy` ID;
- `set_recipient_id`: принудительно выставить конкретный `Addressee` ID;
- `set_counterparty_id`: принудительно выставить конкретный ID корреспондента;
- `forward_email`: переслать исходное письмо как `.eml`-вложение.

Пример:

```json
{
  "name": "Forward letters for recipient 608",
  "enabled": true,
  "when": {
    "recipient_id": 608
  },
  "actions": [
    {
      "type": "forward_email",
      "to": "StryginaVM@taif.ru"
    },
    {
      "type": "skip_directum",
      "reason": "Recipient 608 is handled by email forwarding"
    }
  ]
}
```

Для правил пересылки нужны SMTP-настройки в `login.json`. По умолчанию сервис
использует `username` и `email-password` для SMTP-логина. При необходимости их
можно переопределить через `smtp_username`, `smtp_password` или `forward_from`.

Дневная статистика хранится в `src/data/statistics.sqlite3` по календарному дню
`Europe/Moscow`. Часовой пояс можно изменить через `STATISTICS_TIMEZONE`.
Счетчики идемпотентны по `Message-ID`, поэтому повторная проверка одного и того
же письма не увеличивает счетчик дважды.

## Локальная проверка

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 -m pytest
```

## Идеи для следующих релизов

### Интерфейс

- Дашборд с историей обработки писем.
- Круглые индикаторы состояния для каждого этапа обработки.
- Push-уведомления через WebSocket.
- Окно вывода логов.
- Настраиваемый интервал проверки почты.

### Автоматизация

- Параллельная обработка и очередь задач через Celery + Redis.
- Retry-логика для сбоев.
- Запись ошибок в базу данных.

### Выделение данных

- Более глубокое использование возможностей PaddleOCR.
- Дополнительный лог с OCR-результатами в `.png` с цветовой разметкой.
- Fallback между несколькими моделями для повышения точности.
- Передача темы, отправителя и сырого текста письма в промпты.

### Интеграция Directum

- Переход от RPA-операций к Directum RX API.
- Генерация уведомлений для операторов при сомнительных результатах.
- Автоматические ответы отправителям с номером очереди.

### Безопасность

- Добавить secret manager.
- Шифровать текстовые данные при передаче и хранении.
- Анонимизировать логи.

### Развертывание

- Docker Compose.
- Мониторинг через Prometheus + Grafana.
- GitHub CI/CD.

### Тестирование

- End-to-end тесты на большем количестве примеров.
- Нагрузочное тестирование.
- Поддержание документации в актуальном состоянии.
