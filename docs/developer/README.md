# Обзор для разработчика

TAIF-mail — это приложение на Flask и Socket.IO, которое проверяет общий
почтовый ящик, извлекает данные из входящих PDF-писем, уточняет результат через
локальную модель Ollama и создает входящие письма или задачи в Directum RX.

## Карта репозитория

- `app.py`: Flask-приложение, маршрут `/`, инициализация Socket.IO и фоновый
  цикл проверки почты.
- `src/backend/email_check.py`: IMAP-доступ, декодирование MIME, маршрутизация
  писем, обработка вложений и верхнеуровневая обработка ошибок.
- `src/backend/process_message.py`: последовательный pipeline обработки:
  извлечение текста, AI-выделение данных, создание документа в Directum.
- `src/backend/models.py`: общие dataclass-модели и ошибки валидации.
- `src/backend/directum_rules.py`: движок правил для пропуска обработки,
  пересылки писем и замены ID Directum.
- `src/backend/statistics.py`: дневная статистика в SQLite и отправка обновлений
  через Socket.IO.
- `src/scripts/pdf_parse.py`: конвертация PDF в изображения и OCR через EasyOCR.
- `src/scripts/ai_output_json.py`: вызовы Ollama, загрузка промптов и проверка
  JSON-ответа AI.
- `src/scripts/directum.py`: клиент Directum RX OData, создание входящих писем,
  загрузка вложений и создание задач на проверку.
- `src/scripts/send_error_task.py`: создание задачи в Directum при сбое
  обработки письма.
- `src/scripts/prompts/`: промпты для AI-этапа.
- `src/scripts/directum_rules.json`: локальные редактируемые правила обработки.
  В репозитории этот файл может быть игнорируемым, поэтому перед коммитом
  проверяйте `git status --ignored`.
- `src/frontend/templates/index.html`: единственная HTML-страница и обработчики
  Socket.IO-событий.
- `src/frontend/static/`: CSS, SCSS и изображения интерфейса.
- `tests/`: тесты backend-логики.

## Быстрый вход в проект

1. Прочитайте [Архитектуру](architecture.md), чтобы понять движение письма по
   системе.
2. Прочитайте [Конфигурацию](configuration.md) перед локальным запуском:
   учетные данные разделены между почтой, SMTP-пересылкой, Directum, OCR и
   Ollama.
3. Запустите `python3 -m unittest discover -s tests -p "test_*.py" -v`.
4. Для изменения поведения определите нужный слой:
   - маршрутизация писем: `src/backend/email_check.py`;
   - правила обработки: `src/backend/directum_rules.py`;
   - AI/OCR: `src/scripts/ai_output_json.py` или `src/scripts/pdf_parse.py`;
   - Directum payload/API: `src/scripts/directum.py`;
   - события интерфейса: `src/frontend/templates/index.html`.
5. Добавьте или обновите тесты рядом с изменяемым поведением.

## Принципы разработки

- Pipeline письма должен оставаться явным и последовательным.
- Бизнес-маршрутизацию лучше описывать в `directum_rules.json`. Python-код
  меняется только если нужен новый тип условия или действия.
- Пересылка писем и операции Directum — внешние побочные эффекты. Для них нужны
  понятные логи и тесты.
- Локальные данные не должны попадать в Git: `login.json`, рабочие папки,
  базы статистики и локальные правила могут содержать данные конкретного
  развертывания.

