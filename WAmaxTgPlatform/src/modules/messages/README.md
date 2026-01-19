# Messages Service

Владелец диалогов и сообщений в платформе WAmaxEdu.

## Назначение

Messages Service отвечает за:
- Хранение conversations и messages
- Дедупликацию inbound событий (at-least-once)
- Привязку статусов доставки к сообщениям
- Выдачу данных для UI и Realtime Gateway

## Архитектура

### Входящие события от Integrations Service

- `MessageInboundReceived` - новые входящие сообщения
- `MessageDeliveryStatusUpdated` - обновления статусов доставки

### Дедупликация

**Ключи дедупликации:**
- Сообщения: `channel + accountId + externalMessageRef.id`
- Статусы: `channel + accountId + externalMessageRef.id + status + occurredAt`

### Доменная модель

- **Conversation**: Диалог с участниками
- **Message**: Сообщение с контентом и метаданными
- **MessageDeliveryState**: Текущий статус доставки

## API Endpoints

### Чтение данных

- `GET /conversations?accountId=&channel=` - список диалогов
- `GET /conversations/:id/messages` - сообщения в диалоге
- `GET /messages/:id` - получение сообщения

### Внутренние события

- `MessageCreated` - новое сообщение создано
- `MessageStatusUpdated` - статус доставки обновлен

## Запуск

```bash
npm run dev:server
```

## Тестирование

```bash
npm test
```