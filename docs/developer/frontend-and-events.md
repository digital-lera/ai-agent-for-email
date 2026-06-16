# Фронтенд и Socket.IO-события

## Flask-маршрут

`app.py` содержит один HTTP-маршрут:

- `GET /`: рендерит `src/frontend/templates/index.html`.

При прямом запуске приложение также стартует фоновую задачу проверки почты.

## Жизненный цикл Socket.IO

При подключении backend отправляет текущую дневную статистику через
`statistics_update` и текущий прогресс обработки через `progress_snapshot`.
Поэтому после обновления страницы пользователь видит тот же этап обработки,
который был активен до refresh.

Во время обработки письма backend отправляет события, которые фронтенд
использует для обновления индикаторов прогресса и полей с распознанными
данными.

## События backend

- `statistics_update`: дневные счетчики.
- `progress_snapshot`: полный сохраненный snapshot прогресса при подключении.
- `progress_update`: полный snapshot прогресса после изменения состояния.
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

`progress_snapshot` и `progress_update` являются главным источником состояния
для круглых индикаторов этапов. Старые stage-события оставлены для
совместимости и простого визуального отклика, но восстановление после refresh
работает именно через snapshot из SQLite.

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

После успешного завершения или ошибки backend ждет 10 секунд, затем очищает
сохраненный progress snapshot и отправляет `reset`/`progress_update`.
