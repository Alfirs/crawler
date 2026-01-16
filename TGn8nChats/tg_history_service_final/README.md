# Telegram History Service

FastAPI service that exposes MTProto history endpoints for a Telegram user account (not a bot).
It is intended for n8n workflows that need recent dialogs and message history.

## Requirements
- Python 3.11+
- Telegram api_id / api_hash
- Telethon StringSession

## 1) Get api_id and api_hash
1. Go to https://my.telegram.org/apps
2. Create a new app and copy api_id and api_hash.

## 2) Generate TG_SESSION_STRING
Set env vars and run the helper:

```bash
set TG_API_ID=12345
set TG_API_HASH=abcdef1234567890
python create_session.py
```

On macOS/Linux:

```bash
export TG_API_ID=12345
export TG_API_HASH=abcdef1234567890
python create_session.py
```

Follow prompts for phone number, login code, and 2FA password if enabled.
The script prints a TG_SESSION_STRING. Save it as an environment variable.

## 3) Run with docker-compose

```bash
set TG_API_ID=12345
set TG_API_HASH=abcdef1234567890
set TG_SESSION_STRING=your_session_string
set TG_HISTORY_API_KEY=optional_api_key
docker-compose up --build
```

Service will listen on http://localhost:8088

## 4) API examples

Optional auth header (only if TG_HISTORY_API_KEY is set):

```
X-API-Key: your_api_key
```

Health check:

```bash
curl "http://localhost:8088/health" ^
  -H "X-API-Key: your_api_key"
```

Get dialogs updated in the last 7 days (limit 200):

```bash
curl "http://localhost:8088/tg/getDialogs?days=7&limit=200" ^
  -H "X-API-Key: your_api_key"
```

Get last 50 text messages from a chat:

```bash
curl -X POST "http://localhost:8088/tg/getChatHistory" ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: your_api_key" ^
  -d '{"chatId": 123456789, "count": 50}'
```

## n8n usage
Typical flow:
1) HTTP Request (GET) -> /tg/getDialogs?days=7&limit=200
2) SplitInBatches (by chatId)
3) HTTP Request (POST) -> /tg/getChatHistory with {chatId, count: 50}
4) Your Normalization node
5) GPT
6) Google Sheets

If TG_HISTORY_API_KEY is set, include X-API-Key in both HTTP Request nodes.
