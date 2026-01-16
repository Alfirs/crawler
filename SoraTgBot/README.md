# Sora Telegram Bot

Telegram bot that bulk-generates promo videos for uploaded products via GPT (NeuroAPI) and SORA (kie.ai). Users upload product photos, descriptions, and creative ideas; the bot drafts scripts, requests SORA jobs, downloads the finished videos, and returns them in chat.

## Quick start

1. Copy `.env.example` to `.env` and fill in the tokens.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the bot: `python -m bot.main`.

### Commands / flow

- `/test_script` — quick check that NeuroAPI is reachable.
- `/test_sora` — runs the full GPT → Sora flow with a demo asset and returns task IDs.
- `/tasks [page]` — shows your latest tasks with status and progress counters (pagination supported).
- `/task <task_id>` — detailed progress for a specific task (status + sample subtasks).
- `/tasklog <task_id> [page]` — show the event log for a task (processing history).
- `/settings` — open the per-user settings panel (API keys and model choices).
- `/download_task <task_id>` — get a zip archive (videos + metadata.json) for a finished task.
- `/cancel_task <task_id>` — cancel a pending task; remaining subtasks stop processing.
- `/repeat_task <task_id>` — clone a task (same products/ideas) and enqueue it again.
- `/check_sora <task_id>` — legacy manual sync with Kie.ai (for troubleshooting).
- `/my_products` — list the products you have drafted via the inline menu.

### Per-user settings

Use `/settings` (or the “Настройки” button) to manage your own API keys and preferred models:
- set/clear NeuroAPI key;
- set/clear Sora (Kie.ai) key;
- choose a text model (e.g., `gpt-5-mini`, `gpt-4.1`, `claude-3.5-sonnet`);
- choose a Sora model/variant (e.g., `sora-2-image-to-video`, `sora-2-pro-image-to-video`).

If a field isn’t configured, the bot falls back to the global `.env` values.

Tasks launched through the inline menu are also pushed into the background pipeline automatically: the worker generates scripts via NeuroAPI, queues Sora jobs, polls their status, downloads videos to `storage/tasks/task_<id>/`, and sends the finished files back to Telegram.

In the inline menu:

- «Добавить товар» — start a product form (photo + description).
- «Описание» — edit the current product description.
- «Количество генераций» — set a global number of videos per idea (applies to the whole batch).
- «Добавить идеи» — paste dozens of ideas at once (multi-line or comma-separated).
- «Запустить задачу» — show a summary of all drafts and create a task (subtasks = products × ideas × generation count).
- «Мои задачи» — quick access to `/tasks` via the inline keyboard.
- «Настройки» — open the per-user settings panel without typing `/settings`.
- Быстрый импорт: можно отправить альбом (до 20 фото) — каждое фото станет отдельным черновиком, после чего бот попросит задать описания одной командой.

Uploaded photos are stored under `storage/uploads/<telegram_user_id>/`.
Uploaded photos are stored under `storage/uploads/<telegram_user_id>/`.

## NeuroAPI setup

- Provide `NEUROAPI_API_KEY` in your `.env` file to enable script generation.
- Leave the default base URL (`https://neuroapi.host/v1`) unless you use a custom endpoint.

## Kie.ai (Sora) setup

- Provide `KIE_API_KEY` and keep the base URL as `https://api.kie.ai/api/v1`.
- The bot currently uses `sora-2-image-to-video` via `/jobs/createTask` and polls `/jobs/getTask`.

## Structure
- `bot/` ? entrypoint, config, keyboards, Telegram handlers.
- `core/` ? domain models and DTOs.
- `services/` ? task manager, session storage, GPT/Sora clients, background worker.
- `storage/` ? filesystem layout for tasks (`storage/tasks/`) and uploads (`storage/uploads/`).
