# AI и OCR

## Этап OCR

OCR реализован в `src/scripts/pdf_parse.py`.

`pdf_parse(pdf_files, output_path, config)`:

1. читает настройки OCR из `login.json` и переменных окружения;
2. проверяет доступность CUDA, если запрошен GPU;
3. инициализирует EasyOCR для русского языка;
4. конвертирует страницы PDF в PNG через `pdf2image`;
5. для больших документов пропускает средние страницы после пятой, кроме
   последней;
6. запускает EasyOCR по выбранным страницам;
7. фильтрует фрагменты текста по уверенности;
8. записывает объединенный текст в `output_path`.

Основные настройки:

- `ocr_gpu`;
- `ocr_workers`;
- `ocr_confidence`;
- `ocr_dpi`;
- `ocr_heartbeat_seconds`;
- `OCR_GPU`;
- `OCR_CUDA_DEVICE`.

## Этап AI

AI-извлечение реализовано в `src/scripts/ai_output_json.py`.

`process_text_with_ai(email_content, output_path, attachment_names=())`:

1. читает `prompt_for_preprocessing.txt`;
2. читает `prompt_for_json.txt`;
3. подключается к Ollama;
4. загружает модель, если ее нет локально;
5. выполняет первичную обработку текста;
6. просит модель вернуть строгий JSON;
7. проверяет ответ через `ExtractedData.from_json()`;
8. записывает `processed_data.json`.

Переменные окружения:

- `OLLAMA_HOST`;
- `OLLAMA_MODEL`.

## Контракт извлеченных данных

`ExtractedData` содержит:

- `content`;
- `correspondent`;
- `date_from`;
- `number`;
- `signed_by`;
- `recipient`.

JSON-ключи, ожидаемые от AI:

- `content`;
- `correspondent`;
- `dateFrom`;
- `number`;
- `signedBy`;
- `recipient`.

`content` обязателен. `dateFrom`, если заполнен, должен быть в формате
`DD.MM.YYYY`.

## Сопровождение промптов

Промпты лежат в `src/scripts/prompts/`.

При изменении промптов:

1. сохраняйте ожидаемые JSON-ключи;
2. сохраняйте формат `signedBy` и `recipient`, который подходит для поиска в
   Directum;
3. проверяйте некорректные и пограничные ответы модели;
4. запускайте тесты pipeline.
