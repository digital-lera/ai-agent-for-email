# Архитектура

## Компоненты во время работы

Приложение состоит из пяти основных частей:

- Flask-сервер: отдает страницу `/` из `app.py`.
- Socket.IO-сервер: отправляет в браузер статусы, JSON с распознанными данными,
  ошибки и статистику.
- Фоновый почтовый обработчик: проверяет IMAP каждые 30 секунд.
- Pipeline обработки: OCR, AI-извлечение данных и создание документа в Directum.
- Локальное хранилище: дневная статистика и текущий прогресс обработки в SQLite
  внутри `src/data`.

## Общий поток данных

```text
Браузер
  |
  | GET /
  v
Flask + Socket.IO app.py
  |
  | фоновая задача каждые 30 секунд
  v
email_check.check_email()
  |
  | непрочитанные письма IMAP
  v
_process_one_message()
  |
  | email-level правила могут переслать письмо и остановить обработку
  v
_save_attachments()
  |
  | для обычного pipeline нужен PDF
  v
process_message.run_chain()
  |
  | 1. _extract_text() -> тело письма + OCR
  | 2. _extract_data() -> проверенный ExtractedData
  | 3. _create_document() -> DirectumClient
  v
Directum RX OData API
```

## Рабочие папки писем

Для каждого письма создается отдельная папка в `src/scripts/jobs`. Имя папки —
`MessageContext.job_id`, то есть UUID в hex-формате.

Типичные файлы:

- `email.txt`: объединенный текст письма и OCR.
- `ocr.txt`: текст, распознанный из PDF-вложений.
- `processed_data.json`: проверенный результат AI.
- вложения и временные изображения страниц PDF.

Папка удаляется в блоке `finally` в конце `_process_one_message()`.

## Границы успешной и ошибочной обработки

- Письмо переносится в папку обработанных только после успешного завершения
  выбранного маршрута.
- Обычный успех Directum учитывается как `received` и `successful`.
- Успех Directum с задачей на проверку учитывается как `received` и `partial`.
  Задача на проверку создается, если хотя бы одно JSON-поле карточки письма
  отсутствует, пустое или не сопоставлено с сущностью Directum.
- Если письмо после AI/поиска Directum переслано в приемную получателя по
  `recipient_id` и документ Directum не создается, оно учитывается как
  `received` и `forwarded_recipient`.
- Ошибка pipeline после принятия письма учитывается как `received` и `manual`
  только если удалось создать задачу об ошибке в Directum.
- Email-level правила с `skip_directum` считаются успешным маршрутом и не
  запускают OCR, AI и создание документа Directum.

## Модель статусов Socket.IO

Backend отправляет укрупненные события:

- `reset`
- `new_email`
- `filename_recognized`
- `text_parse_started` / `text_parse_finished`
- `ai_data_recognition_started` / `ai_data_recognition_finished`
- `directum_api_started` / `directum_api_finished`
- `json_data_received`
- `chain_update`
- `chain_complete`
- `progress_snapshot`
- `progress_update`
- `statistics_update`
- `error`

Браузер только отображает актуальное состояние. Источник состояния — backend.
При подключении или обновлении страницы frontend получает `progress_snapshot`
из SQLite и восстанавливает прогресс текущего письма. После успешного
завершения или ошибки backend через 10 секунд очищает сохраненный прогресс и
отправляет `reset`/`progress_update`.
