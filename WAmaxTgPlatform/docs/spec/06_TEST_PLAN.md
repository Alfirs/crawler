# Platform E2E & Integration Test Plan v1.0
## Status
Draft

Back: [00_INDEX](00_INDEX.md)

## Current test inventory (repo snapshot)
- Integrations integration test exists and exercises `/health`, outbound send, inbound webhook, and channel health (src/modules/integrations/test/integration.test.ts).
- `npm test` runs the Integrations integration test with local/test env overrides (../../package.json).

## Test strategy (v1.0)
### Unit tests
- Integrations:
  - Idempotency hash stability and conflict detection (src/modules/integrations/src/services/idempotency.service.ts, src/modules/integrations/src/services/outbound-message.service.ts).
  - Provider payload normalization for representative payloads (src/modules/integrations/src/services/inbound-webhook.service.ts).
- Messages:
  - Dedup key generation and behavior on duplicates (src/modules/messages/src/services/dedup.service.ts, src/modules/messages/src/services/message-processing.service.ts).

### Integration tests (HTTP + broker + Redis)
- Integrations HTTP (already present): validate required header behavior, schema validation errors, and 202/200 responses (src/modules/integrations/test/integration.test.ts, src/modules/integrations/src/controllers/*.ts).
- Integrations + Redis idempotency:
  - Run with `REDIS_ENABLED=true` and `IDEMPOTENCY_STORE=redis` and validate repeat calls return identical responses (src/modules/integrations/src/services/idempotency.service.ts, src/config/redis.config.ts).
- Integrations + RabbitMQ publish:
  - Run with `RABBITMQ_ENABLED=true` and ensure publishes succeed (src/modules/integrations/src/services/event-publisher.service.ts, src/config/env.config.ts).
- Messages + broker consume:
  - TODO: implement broker-backed consumption; current subscribe path is in-memory only (src/modules/messages/src/services/integration-event-subscriber.service.ts, src/modules/integrations/src/services/event-publisher.service.ts).

### Contract tests (DTOs/events)
- Type-level compilation check (`tsc --noEmit`) for DTO/event interfaces referenced in API contracts (../../package.json, ../../tsconfig.json, src/modules/integrations/src/events/*, src/modules/integrations/src/dto/*, src/modules/messages/src/dto/*).
- Schema validation coverage for outbound send request payloads (src/modules/integrations/src/validate/outbound-message.schema.ts, src/modules/integrations/src/middleware/validation.middleware.ts).

### Negative tests (required)
- Idempotency conflict:
  - Same `Idempotency-Key` with different body returns `409 IDEMPOTENCY_CONFLICT` (src/modules/integrations/src/services/outbound-message.service.ts, src/modules/integrations/src/controllers/outbound-message.controller.ts).
- Missing idempotency key:
  - Missing header returns `400 MISSING_IDEMPOTENCY_KEY` (src/modules/integrations/src/controllers/outbound-message.controller.ts).
- Unsupported channel / connect mode:
  - `channel !== "WHATSAPP"` → `422 UNSUPPORTED_CHANNEL` (src/modules/integrations/src/controllers/outbound-message.controller.ts, src/modules/integrations/src/controllers/channel.controller.ts).
  - `mode !== "NEW"` → `422 UNSUPPORTED_CONNECT_MODE` (src/modules/integrations/src/controllers/channel.controller.ts).
- Invalid provider payload:
  - Malformed webhook/status payload returns `400 INVALID_PROVIDER_PAYLOAD` (src/modules/integrations/src/controllers/inbound-webhook.controller.ts, src/modules/integrations/src/services/inbound-webhook.service.ts).

### Leakage tests (policy)
- Ensure provider-specific tokens do not appear outside Integrations (src/modules/integrations/src/services/inbound-webhook.service.ts):
  - `rg -n \"evolution-api|baileys\" src/modules -g\"!src/modules/integrations/**\"`

## Local verification runbook (PowerShell-friendly; not executed here)
### Fast path (runs existing test)
```powershell
npm test
```
(../../package.json, src/modules/integrations/test/integration.test.ts)

### Manual smoke (Integrations service)
```powershell
# 1) Set minimal env (adjust URIs as needed)
$env:NODE_ENV='development'
$env:PORT='3001'
$env:REDIS_ENABLED='0'
$env:RABBITMQ_ENABLED='0'
$env:IDEMPOTENCY_STORE='memory'

# 2) Start Integrations service
tsx src/modules/integrations/src/main.ts
```
(src/modules/integrations/src/main.ts, src/config/env.config.ts)

Then, in another shell:
```powershell
# Health
Invoke-RestMethod http://localhost:3001/health
```
(src/modules/integrations/src/main.ts)

## TODO (missing to complete v1.0 test plan)
- Add integration tests for Messages and Realtime services (standalone entrypoints now exist) (src/modules/messages/src/main.ts, src/modules/realtime/src/main.ts).
- Add broker-backed integration tests for Messages/Realtimes queue consumption (src/modules/messages/src/services/integration-event-subscriber.service.ts, src/modules/realtime/src/services/message-event-subscriber.service.ts).
- Provide Prisma migrations required for DB-backed tests (schemas added, migrations pending) (./prisma/*-schema.prisma).
