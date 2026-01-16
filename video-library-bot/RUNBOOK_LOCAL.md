# RUNBOOK_LOCAL

Локальный запуск Video Library Bot на Windows.

## 1. Требования

- Windows 10/11
- Python 3.11+
- Telegram Bot токен (получить у @BotFather)
- Yandex.Disk OAuth токен

## 2. Быстрый старт

```powershell
cd D:\VsCode\YNDXtgPars\video-library-bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
notepad .env
python -m app.main
```

## 3. Конфигурация (.env)

```ini
# Обязательные
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
YANDEX_DISK_OAUTH_TOKEN=y0_AgAAAA...

# Опциональные
ADMIN_USER_IDS=123456789,987654321
YANDEX_DISK_ROOT=disk:/VideoLibrary
SCAN_INTERVAL_SEC=300
STABILITY_CHECK_SEC=30
SIM_THRESHOLD=0.30
LEXICAL_BOOST=0.15
TOP_K=3
TELEGRAM_SEND_MAX_MB=45
DATA_DIR=./data
AUTO_META_MODE=write
ENABLE_TRANSCRIPTION=0
TRANSCRIBE_MODEL=small
SEED_SAMPLE_VIDEO_PATH=
CHAOS_MODE=0
CHAOS_RATE=0.15
```

`MAX_TELEGRAM_UPLOAD_MB` поддерживается для совместимости, но предпочтительно использовать `TELEGRAM_SEND_MAX_MB`.

## 4. Получение Yandex.Disk OAuth токена

1. Создайте приложение: https://oauth.yandex.com/client/new
   - Платформа: Веб-сервисы
   - Права: `cloud_api:disk.read`, `cloud_api:disk.write`
2. Получите `Client ID`
3. Откройте URL (замените `<CLIENT_ID>`):
   ```
   https://oauth.yandex.com/authorize?response_type=token&client_id=<CLIENT_ID>
   ```
4. Скопируйте `access_token` из URL после редиректа
5. Вставьте токен в `.env`

## 5. Создание папки VideoLibrary на Яндекс.Диске

1. Откройте https://disk.yandex.ru и создайте папку `VideoLibrary` в корне.
2. В `.env` укажите путь:
   ```
   YANDEX_DISK_ROOT=disk:/VideoLibrary
   ```

## 6. Как добавить видео (UI Яндекс.Диска)

### Pattern A (предпочтительно)
```
disk:/VideoLibrary/<AnyFolderTitle>/
    video.mp4
    description.txt   (опционально)
    title.txt         (опционально)
```

### Pattern B (часто бывает)
```
disk:/VideoLibrary/<title>.mp4
```

Сканер сам создаст папку `<title>` и переместит файл внутрь.

## 7. Авто-метаданные

- Если `meta.json` отсутствует, он создается автоматически (если `AUTO_META_MODE=write`).
- Если `summary.md` отсутствует, он создается из `title.txt`/имени папки + `description.txt`.
- Файл `disk:/VideoLibrary/library_index.json` обновляется после сканирования.

## 8. Проверка подключения

### Тест Yandex.Disk
```powershell
python -m scripts.test_storage
```

### Демо-наполнение
```powershell
python -m scripts.seed_demo
```

### Тест сканирования и поиска
```powershell
python -m scripts.test_search
python -m scripts.edge_cases
python -m scripts.chaos_smoke
```

Если библиотека пустая, скрипт выведет `library empty` и завершится без ошибки.

CHAOS_MODE включается автоматически внутри `scripts.chaos_smoke` и не влияет на прод по умолчанию.

## 9. Запуск бота

```powershell
python -m app.main
```

Бот запускает:
1) Фоновое сканирование `SCAN_INTERVAL_SEC`
2) Автоматическую индексацию
3) Telegram обработчики

## 10. Команды администратора

Добавьте свой Telegram ID в `ADMIN_USER_IDS`:

```ini
ADMIN_USER_IDS=123456789
```

Команды:
- `/admin_status` - статистика + последние ошибки
- `/reindex` - полная переиндексация
- `/reindex <video_id>` - переиндексация одного видео
- `/add_video` - загрузка видео через Telegram
- `/selftest` - прогон стандартных запросов
- `/seed_demo` - демо-наполнение + selftest
- `/health` - быстрый health snapshot

## 11. Примеры запросов пользователя

- дай мне видео с руинами
- как пользоваться пером
- разбор мазей

## 12. Транскрипция (опционально)

1. Установите ffmpeg и добавьте в `PATH`
2. Установите faster-whisper:
   ```powershell
   pip install faster-whisper
   ```
3. В `.env` включите:
   ```ini
   ENABLE_TRANSCRIPTION=1
   TRANSCRIBE_MODEL=small
   ```

Если зависимости отсутствуют, бот логирует предупреждение и продолжает работу.

## 13. Полный чек

```powershell
.\check.ps1
```

Скрипт запускает:
- `python -m compileall app scripts`
- `python -m scripts.test_storage`
- `python -m scripts.seed_demo`
- `python -m scripts.test_search`
- `python -m scripts.smoke_user_queries`
- `python -m scripts.edge_cases`
- `python -m scripts.chaos_smoke`
- `python -m scripts.audit_all`

## 14. Логи

Формат:
```
2026-01-14 04:00:00,123 [INFO] video_library_bot.scan: scan started
2026-01-14 04:00:05,456 [INFO] video_library_bot.scan: scan report
2026-01-14 04:00:05,789 [INFO] video_library_bot.index: indexed video
```

## 15. Устранение неполадок

| Проблема | Решение |
|----------|---------|
| `TELEGRAM_BOT_TOKEN is not set` | Заполните токен в `.env` |
| `token_ok=False` | Проверьте Yandex.Disk токен |
| `YANDEX_DISK_ROOT not found` | Проверьте путь и наличие папки на диске |
| `meta.json` не создается | Проверьте права записи и `AUTO_META_MODE` |
| Видео не отправляется | Проверьте размер файла и права доступа |
| Индекс пустой | Убедитесь, что есть видео со статусом READY |
| `transcription disabled: ffmpeg not found` | Установите ffmpeg или выключите `ENABLE_TRANSCRIPTION` |
| Warning about HuggingFace symlinks | Установите `HF_HUB_DISABLE_SYMLINKS_WARNING=1` |

## 18. Manual E2E checklist

1. `python -m app.main`
2. В Telegram: `/seed_demo`
3. `/selftest`
4. Запросы:
   - "дай мне видео с руинами"
   - "разбор мазей"
   - "как пользоваться пером"
5. Нажать “Отправить” и проверить доставку (файл или ссылка)

## 16. Полезные команды

```powershell
python -m scripts.test_storage
python -m scripts.seed_demo
python -m scripts.test_search
python -m scripts.smoke_user_queries
.\check.ps1
python -m app.main
```

## 17. Структура данных

```
data/
├── video_library.db
└── txtai_index/
    ├── config
    ├── embeddings
    ├── documents
    └── index_version.json
```
