# Startup Runbook (v1.0)

## Prereqs
- Node.js 18+
- PostgreSQL or MySQL (for MESSAGE_STORE=database)
- Redis (optional unless IDEMPOTENCY_STORE=redis)
- RabbitMQ (required in production)

## Common env (examples)
```
NODE_ENV=development
PORT=3000
DATABASE_CONNECTION_URI=postgresql://user:password@localhost:5432/wamaxedu
MESSAGE_STORE=memory
SKIP_DB=1
REDIS_ENABLED=false
IDEMPOTENCY_STORE=memory
RABBITMQ_ENABLED=false
AUTH_REQUIRED=false
WHATSAPP_PROVIDER_BASE_URL=http://localhost:8080
WHATSAPP_PROVIDER_API_KEY=your-provider-api-key
WHATSAPP_PROVIDER_WEBHOOK_URL=http://localhost:3001/integrations/whatsapp/inbound/provider-webhook
WHATSAPP_PROVIDER_WEBHOOK_EVENTS=messages.upsert,send.message.update
WHATSAPP_PROVIDER_WEBHOOK_BY_EVENTS=false
```

## Monolith (all HTTP APIs in one process)
```
npm run start
```
- Integrations: `http://localhost:3000/api/v1/integrations/*`
- Messages: `http://localhost:3000/api/v1/messages/*`
- Auth: `http://localhost:3000/api/v1/auth/*`
- Health: `http://localhost:3000/health`

## Dedicated services
```
tsx src/modules/integrations/src/main.ts
tsx src/modules/messages/src/main.ts
tsx src/modules/auth/src/main.ts
tsx src/modules/realtime/src/main.ts
```
- Integrations health: `http://localhost:3001/health`
- Messages health: `http://localhost:3002/health`
- Realtime health: `http://localhost:3003/health`
- Auth health: `http://localhost:3004/health`

## Production guidance
- Set `RABBITMQ_ENABLED=true` and `RABBITMQ_URI=...`
- Set `MESSAGE_STORE=database` with a live DB
- Keep `AUTH_REQUIRED=true` for protected endpoints

## Database schema (Prisma)
```
set DATABASE_PROVIDER=postgresql
npm run db:generate
npm run db:migrate:dev
```
