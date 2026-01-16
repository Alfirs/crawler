# DraftClone

Local playground inspired by getdraft.io. The new flow focuses on a text-first editor: the API builds an outline from your prompt, stores it as structured JSON and immediately opens an interactive editor where you can tweak slides, typography, layouts, backgrounds and export later. No GPT-4o image rendering or Redis queues are required anymore.

## Requirements

- Python 3.11+
- (optional) Telegram Bot API token if you plan to run `bot/bot.py`

## Setup

```bash
python -m venv .venv
. .venv/Scripts/activate      # Windows PowerShell syntax
pip install -r requirements.txt
```

Copy `.env.example` → `.env` and fill at least:

- `APP_URL` – usually `http://localhost:8000`
- `JWT_SECRET` – any random string
- `OPENAI_API_KEY` – optional; without it the app falls back to a template outline
- `TELEGRAM_BOT_TOKEN` – only if you want to use the Telegram bot

Other useful flags: `MAX_IDEA_CHARS`, `DEFAULT_THEME`, `JWT_TTL_MIN`.

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# optional bot (talks to /api/generate and sends the editor link)
python bot/bot.py
```

`worker.py` is no longer used; background queues and Redis are gone. Instead the React editor lives in `frontend/`, run `npm install && npm run build` to generate `/app/static/frontend`.

## API

- `POST /api/generate` – body `{"format":"carousel","slides":6,"source":{"kind":"text","text":"..."}, "theme":"sunrise"}`. Returns `{ "post_id": 12, "status": "ready", "share_url": ".../posts/12/editor?token=...", "token": "..." }`.
- `GET /api/posts/{id}` – metadata (`status`, `slides`, `theme`, `share_url`).
- `GET /api/posts/{id}/editor?token=...` – full JSON for the editor (slides + settings). Used by the frontend and exported as the new share endpoint.
- `PATCH /api/posts/{id}?token=...` – update slides/settings; saves immediately.
- `GET /posts/{id}/editor?token=...` – HTML editor UI (Templates / Background / Text / Layout / Size / Info / Export tabs).
- `POST /api/posts/{id}/export?token=...` – placeholder endpoint for PNG/PDF export (returns `status: "not_implemented"` for now).

## Editor

The editor lives in `/frontend` (React + Vite). Build output is served via `app/templates/editor_shell.html`.

- Slide gallery with quick preview.
- Drag–drop reordering, inline rename.
- Inspector panel to edit title, subtitle, body, bullets, notes, “apply to all” toggles, AI action placeholders.
- Theme picker backed by the palette defined in `app/themes.py`.
- Share-link panel so you can copy the editor URL for collaborators.
- Inline WYSIWYG editing directly on the preview canvas and a basic undo/redo stack.

All data is stored as JSON inside the `Post` record, so edits are instant and visible in `/api/posts/{id}/editor`.

## Telegram bot

`bot/bot.py` asks for slide count + idea text, calls `/api/generate` and immediately replies with the editor URL. No polling or background jobs.

## Roadmap

- More tabs/tools inside the editor (background gradients, typography presets, export options).
- Optional attachment uploads per slide.
- Server-side export (PDF/PNG) once the editor schema stabilises.
