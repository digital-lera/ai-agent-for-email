# Фронтенд и Socket.IO-события

## Flask-маршрут

`app.py` содержит один HTTP-маршрут:

- `GET /`: рендерит `src/frontend/templates/index.html`.

При прямом запуске приложение также стартует фоновую задачу проверки почты.

## Жизненный цикл Socket.IO

При подключении backend отправляет текущую дневную статистику через
`statistics_update`.

Во время обработки письма backend отправляет события, которые фронтенд
использует для обновления индикаторов прогресса и полей с распознанными
данными.

## События backend

- `statistics_update`: дневные счетчики.
- `reset`: очистка текущего состояния интерфейса перед новым письмом.
- `new_email`: отображение темы и отправителя.
- `filename_recognized`: отображение имени найденного вложения.
- `chain_update`: активный этап и текст лога.
- `text_parse_started` / `text_parse_finished`: этап распознавания текста.
- `ai_data_recognition_started` / `ai_data_recognition_finished`: этап AI.
- `directum_api_started` / `directum_api_finished`: этап Directum.
- `json_data_received`: поля письма, выделенные AI.
- `chain_complete`: ID документа после завершения pipeline.
- `error`: отображение общего состояния ошибки.

## Файлы фронтенда

- `src/frontend/templates/index.html`: разметка и inline-обработчики Socket.IO.
- `src/frontend/static/styles/style.css`: скомпилированный CSS.
- `src/frontend/static/styles/style.scss`: SCSS-источник.
- `src/frontend/static/styles/sass_sources/`: SCSS-фрагменты.
- `src/frontend/static/styles/images/`: логотипы и иконки статусов.

## Изменение состояния интерфейса

Если добавляется новое backend-событие:

1. отправляйте его из backend в одной понятной точке;
2. добавьте обработчик в `index.html`;
3. очищайте связанное состояние в обработчике `reset`;
4. не смешивайте события статистики и события pipeline.

