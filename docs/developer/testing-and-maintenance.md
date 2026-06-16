# Тестирование и сопровождение

## Команды проверки

Запуск всех unit-тестов:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

Если установлен `pytest`, проект также поддерживает:

```bash
python3 -m pytest
```

Проверка синтаксиса измененных Python-файлов:

```bash
python3 -m py_compile path/to/file.py
```

Проверка JSON-файла правил:

```bash
python3 -m json.tool src/scripts/directum_rules.json
```

## Структура тестов

- `tests/test_models.py`: валидация и контракты данных.
- `tests/test_email_utils.py`: MIME-декодирование и безопасность имен файлов.
- `tests/test_process_message.py`: события и результаты pipeline.
- `tests/test_directum_client.py`: payload Directum, поиск, задачи и
  конфигурация.
- `tests/test_directum_rules.py`: сопоставление правил, решения о пересылке,
  замены ID и пропуск Directum.
- `tests/test_statistics.py`: идемпотентность счетчиков SQLite.
- `tests/test_statistics_lifecycle.py`: итоговые счетчики для маршрутов письма.
- `tests/test_send_error_task.py`: payload задачи об ошибке Directum.
- `tests/email_test.py` и `tests/directum_test.py`: опциональные проверки живых
  сервисов, запускаются только при передаче учетных данных.

## Типовые сценарии изменений

### Добавить новое правило маршрутизации письма

1. Сначала попробуйте отредактировать `src/scripts/directum_rules.json`.
2. Если нужного условия или действия нет, добавьте его в
   `src/backend/directum_rules.py`.
3. Добавьте тесты движка правил в `tests/test_directum_rules.py`.
4. Если меняется поведение приема письма, добавьте lifecycle-тест в
   `tests/test_statistics_lifecycle.py`.

### Изменить поля Directum

1. Обновите формирование payload в `src/scripts/directum.py`.
2. Обновите или добавьте тесты в `tests/test_directum_client.py`.
3. Проверьте, что ошибки поиска Directum по-прежнему создают задачу на
   проверку.

### Изменить AI-результат

1. Обновите промпты.
2. Если меняется контракт, обновите валидацию `ExtractedData`.
3. Обновите `tests/test_models.py` и тесты pipeline.

### Изменить статистику

1. Обновите `COUNTER_COLUMNS` и `COUNTER_GROUPS`.
2. Если меняется схема SQLite, добавьте миграционную логику.
3. Обновите отображение на фронтенде и тесты статистики.

## Git-гигиена

Перед передачей изменений проверьте:

```bash
git status --short
git status --ignored --short src/scripts/directum_rules.json
```

Следите за локальными сгенерированными файлами:

- `src/scripts/jobs/`;
- `src/data/statistics.sqlite3`;
- `__pycache__/`;
- локальный `login.json`;
- возможно игнорируемый `directum_rules.json`.

