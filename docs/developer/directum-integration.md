# Интеграция с Directum

Поведение Directum разделено между файлами:

- `src/scripts/directum.py`: API-клиент и операции с документами/задачами
  Directum.
- `src/backend/directum_rules.py`: загрузка правил, сопоставление условий,
  пересылка писем и решения по ID.
- `src/scripts/send_error_task.py`: создание задачи при ошибке обработки.

## DirectumClient

`DirectumClient.from_config(config)` читает:

- `odataurl`;
- `directum-username`;
- `password`;
- `performer_id`;
- `request_timeout`;
- `directum_rules_path`.

Клиент настраивает `requests.Session.auth` и отключает TLS verification,
потому что для этого развертывания требуется `verify=False`.

## Создание входящего письма

`create_incoming_letter(data, attachments, context=None)`:

1. ищет `SignedBy` в `IContacts`;
2. ищет `Addressee` в `IEmployees`;
3. ищет корреспондента в `ICounterparties`;
4. применяет правила уровня Directum ID;
5. при необходимости пересылает письмо и пропускает создание документа;
6. формирует payload для `IIncomingLetters`;
7. загружает PDF-вложения как версии документа;
8. создает задачу на проверку, если были ошибки сопоставления.
9. если ошибок сопоставления не было, создает простую задачу с просьбой
   направить готовое письмо по маршруту.

## Нечеткий поиск в Directum

`find_fuzzy_id()` сравнивает нормализованное имя с кандидатами из Directum. Для
людей используется ключ вида `Фамилия И`. Порог по умолчанию — `80`.

Если поле было в AI-результате, но ID не найден, клиент сохраняет ошибку и
после создания документа делает задачу на проверку.

## Схема файла правил

Правила — это JSON-объекты в списке `rules`:

```json
{
  "name": "Forward resume letters by text",
  "enabled": true,
  "when": {
    "text_contains_any": ["резюме", "кандидат", "CV"]
  },
  "actions": [
    {"type": "forward_email", "to": "MikhelAA@taif.ru"},
    {
      "type": "skip_directum",
      "reason": "Resume letter is handled by email forwarding"
    }
  ]
}
```

Условия уровня письма:

- `sender_email`;
- `sender_contains`;
- `text_contains_any`;
- `attachment_name_contains_any`.

Условия уровня ID Directum:

- `signed_by_id`;
- `recipient_id`;
- `counterparty_id`;
- `any_id`.

Действия:

- `forward_email`;
- `skip_directum`;
- `replace_matched_id`;
- `set_signed_by_id`;
- `set_recipient_id`;
- `set_counterparty_id`.

## Важная семантика правил

Условия внутри одного правила объединяются логическим И. Если поведение должно
срабатывать по тексту ИЛИ имени вложения, создайте два правила с одинаковыми
действиями.

Email-level `skip_directum` останавливает OCR, AI и создание документа Directum.

ID-level `skip_directum` выполняется после OCR, AI и поиска в Directum. Он
предотвращает создание входящего письма, но предыдущие этапы уже выполнены.

`forward_email` отправляет исходное письмо как вложение `.eml`.

## Настройки пересылки

Пересылка использует SMTP-настройки из `login.json`:

- `smtp_server`;
- `smtp_port`;
- `smtp_use_tls`;
- необязательный `smtp_username`;
- необязательный `smtp_password`;
- необязательный `forward_from`.

Если SMTP-учетные данные не переопределены, используются почтовые учетные
данные: `username` и `email-password`.

## Задачи на проверку и задачи об ошибке

Задачи на проверку создаются, когда документ в Directum создан, но часть данных
не удалось сопоставить уверенно.

Задачи успешной обработки создаются, когда документ в Directum создан без
ошибок сопоставления. Текст задачи: `Письмо было обработано успешно, все поля
внесены в карточку ИИ-агентом. Пожалуйста, направьте готовое письмо по
маршруту`.

Задачи об ошибке создаются, когда pipeline письма падает. Они не привязаны к
документу, потому что документ мог не быть создан.
