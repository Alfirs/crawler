# Evolution API Troubleshooting Guide

## WhatsApp Pairing Issues

### Problem: QR Code Scanning Fails ("не удалось связать устройство")

**Симптомы:**
- При сканировании QR-кода появляется ошибка "не удалось связать устройство"
- QR-код генерируется, но связывание не происходит
- В логах `pairingCode: null`

**Причина:**
Проблема возникает когда параметр `number` не передаётся при создании инстанса или подключении. Без номера телефона API генерирует только QR-код, но не pairing code.

**Решение: Использовать Pairing Code вместо QR-кода**

1. **Удалить существующий инстанс:**
```bash
curl -X DELETE http://localhost:8080/instance/delete/wamaxedu \
  -H "apikey: YOUR_API_KEY"
```

2. **Создать новый инстанс с номером телефона:**
```bash
curl -X POST http://localhost:8080/instance/create \
  -H "apikey: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "wamaxedu",
    "qrcode": true,
    "number": "79010535205",
    "integration": "WHATSAPP-BAILEYS"
  }'
```

3. **Получить pairing code:**
```bash
curl -X GET http://localhost:8080/instance/connect/wamaxedu \
  -H "apikey: YOUR_API_KEY"
```

В ответе будет поле `pairingCode` (например: `54NHHJ7L`)

4. **Ввести код в WhatsApp:**
   - Настройки → Связанные устройства
   - "Связать устройство"
   - Выбрать "Связать по номеру телефона" (внизу экрана)
   - Ввести полученный код

---

### Problem: API Key 401 Unauthorized

**Симптомы:**
- Ошибка `{"status":401,"error":"Unauthorized"}`

**Решение:**
Проверить API ключ в `.env` файле:
```
AUTHENTICATION_API_KEY=wamaxedu_evolution_key_change_me_in_production
```

Использовать этот ключ в заголовке `apikey`.

---

### Problem: Webhook ECONNREFUSED Errors

**Симптомы:**
- В логах ошибки `ECONNREFUSED` к `http://localhost:3000/...`

**Причина:**
Настроен webhook на несуществующий сервер.

**Решение:**
Эти ошибки можно игнорировать для локальной разработки. Для production настройте корректный webhook URL в параметрах инстанса.

---

## Полезные API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/instance/create` | POST | Создать инстанс |
| `/instance/connect/:name` | GET | Подключиться (получить QR/pairing code) |
| `/instance/connectionState/:name` | GET | Статус подключения |
| `/instance/logout/:name` | DELETE | Выйти из сессии |
| `/instance/delete/:name` | DELETE | Удалить инстанс |

---

## Конфигурация

**Файл:** `evolution-api-main/.env`

Ключевые параметры:
- `SERVER_PORT=8080` - порт API
- `AUTHENTICATION_API_KEY` - ключ авторизации
- `DATABASE_CONNECTION_URI` - подключение к PostgreSQL
