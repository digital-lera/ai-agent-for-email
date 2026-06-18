# AI и OCR

## Этап получения текста PDF

Получение текста PDF реализовано в `src/scripts/pdf_parse.py`.

`pdf_parse(pdf_files, output_path, config)`:

1. проверяет PDF на встроенный текст через `pdftotext`;
2. если встроенного текста достаточно, записывает его в `output_path` и не
   запускает OCR;
3. если встроенного текста нет или его слишком мало, читает настройки OCR из
   `login.json` и переменных окружения;
4. проверяет доступность CUDA, если запрошен GPU;
5. инициализирует EasyOCR для русского языка;
6. конвертирует страницы PDF в PNG через `pdf2image`;
7. для больших документов пропускает средние страницы после пятой, кроме
   последней;
8. запускает EasyOCR по выбранным страницам;
9. фильтрует фрагменты текста по уверенности;
10. записывает объединенный текст в `output_path`.

Основные настройки:

- `embedded_pdf_text_min_chars`;
- `ocr_gpu`;
- `ocr_workers`;
- `ocr_confidence`;
- `ocr_dpi`;
- `ocr_heartbeat_seconds`;
- `ocr_model_storage_dir`;
- `OCR_GPU`;
- `OCR_CUDA_DEVICE`;
- `OCR_MODEL_STORAGE_DIR`.

EasyOCR скачивает detection и recognition модели при первой инициализации.
Чтобы не скачивать их заново после перезапуска контейнера, приложение передает
`model_storage_directory` в `easyocr.Reader()`. По умолчанию используется
`/root/.EasyOCR/model`, а Docker Compose монтирует `/root/.EasyOCR` в named
volume `easyocr`.

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
- `inn`;
- `date_from`;
- `number`;
- `signed_by`;
- `recipient`.

JSON-ключи, ожидаемые от AI:

- `content`;
- `correspondent`;
- `inn`;
- `dateFrom`;
- `number`;
- `signedBy`;
- `recipient`.

`content` обязателен. `inn`, если заполнен, должен состоять из 10 или 12
цифр. `dateFrom`, если заполнен, должен быть в формате `DD.MM.YYYY`.

## Сопровождение промптов

Промпты лежат в `src/scripts/prompts/`.

При изменении промптов:

1. сохраняйте ожидаемые JSON-ключи;
2. сохраняйте формат `inn`, `signedBy` и `recipient`, который подходит для поиска в
   Directum;
3. проверяйте некорректные и пограничные ответы модели;
4. запускайте тесты pipeline.
