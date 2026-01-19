# 🧪 Шпаргалка по тестированию

## Быстрый старт

```bash
# Запустить сервис
npm run start:integrations
```

---

## Тест 1: WhatsApp → Bitrix24

```powershell
curl -X POST http://localhost:3000/integrations/whatsapp/inbound/provider-webhook `
  -H "Content-Type: application/json" `
  -d '{
    "event": "messages.upsert",
    "data": {
      "key": {"remoteJid": "79991234567@s.whatsapp.net", "fromMe": false, "id": "TEST1"},
      "pushName": "Test User",
      "message": {"conversation": "Hello from WhatsApp!"}
    },
    "instance": "wamaxedu"
  }'
```

**Результат:** В Bitrix24 появится чат "WhatsApp: Test User"

---

## Тест 2: MAX → Bitrix24

```powershell
curl -X POST http://localhost:3000/integrations/max/webhook `
  -H "Content-Type: application/json" `
  -d '{
    "event": "message_new",
    "data": {
      "chat_id": "max_chat_123",
      "from_user": "Max User",
      "text": "Hello from MAX!"
    }
  }'
```

**Результат:** В Bitrix24 появится чат "MAX: Max User"

---

## Тест 3: Bitrix24 → WhatsApp/MAX (Обратный поток)

1. Открой Bitrix24 → Чаты
2. Найди созданный чат
3. Напиши ответ
4. Через 5 секунд система попытается отправить его клиенту

**Требования:**
- Для WhatsApp: должен быть запущен Evolution API
- Для MAX: должен быть указан MAX_BOT_TOKEN в .env

---

## Логи

```powershell
# Смотреть логи в реальном времени
Get-Content -Wait -Tail 20 integrations_service_v12.log
```
