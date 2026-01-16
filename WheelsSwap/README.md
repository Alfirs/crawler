# WheelSwap Bot

Телеграм-бот, который помогает «примерить» разные диски на автомобиль. Минимальная логика выполняется локально, а генерация выполняется через Seedream V4 Edit и текстовую модель (например, `nano-banana-pro`) на платформе kie.ai.

## Подготовка окружения

1. Создайте файл `.env` и заполните ключевые переменные:
   ```env
   TELEGRAM_BOT_TOKEN=<ваш токен бота>
   KIE_API_KEY=<api-ключ kie.ai>
   KIE_BASE_URL=https://api.kie.ai/api/v1
   SEEDREAM_MODEL_NAME=bytedance/seedream-v4-edit
   SEEDREAM_RENDER_MODEL_NAME=nano-banana-pro
   RENDER_ASPECT_RATIO=16:9
   RENDER_RESOLUTION=2K
   RENDER_OUTPUT_FORMAT=jpg
   KIE_UPLOAD_BASE_URL=https://kieai.redpandaai.co
   KIE_UPLOAD_PATH=wheel-swap
   BASE_MEDIA_DIR=./media
   ```
2. Установите Python 3.11+ и зависимости: `pip install -r requirements.txt`.
3. По желанию используйте `docker compose up --build` для запуска в контейнерах.

## Запуск
```
python -m bot.main
```
Бот сохраняет промежуточные файлы в каталоге `BASE_MEDIA_DIR` (по умолчанию `./media`). Подкаталоги `originals`, `masks`, `results`, `temp` создаются автоматически.

## Как работает бот
1. Пользователь отправляет `/start` и фотографию автомобиля строго сбоку, чтобы были видны оба колеса.
2. Затем отправляет фото диска (можно с подписью).
3. Бот предлагает выбрать режим:
   - **Быстрая примерка** — выполняется Seedream Edit на исходном фото. Меняются только маски колес, кузов/цвет/фон остаются прежними.
   - **Каталожный рендер** — используется текстовая модель, которая генерирует рекламный кадр, но цвет кузова приводится к оригиналу с помощью дополнительной цветокоррекции.
4. После обработки бот отправляет готовое изображение. В случае ошибок показывается понятное сообщение, а исходные временные файлы удаляются.

## HTTP API
- `GET /api/wheels` — список доступных дисков (id, name, short_description, style_prompt).
- `POST /api/fit-wheels` — быстрая примерка (multipart: `file` — фото авто, `wheel_photo` — фото диска, `wheel_id` — опционально).
- `POST /api/render-catalog` — каталожный рендер (multipart: `file`, `wheel_id`, опционально `wheel_reference`).

Оба эндпоинта возвращают JSON с `request_id` и `result_url`, откуда можно скачать готовое изображение.

## Тесты
```
python -m pytest
```

## Структура проекта
- `app/` — FastAPI-приложение, работа с kie.ai, обработка изображений.
- `bot/` — Telegram-бот (aiogram v3).
- `tests/` — базовые тесты для утилитарных функций.
- `media/` — рабочие файлы (может отсутствовать до первого запуска).
