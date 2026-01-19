# Acceptance Criteria (v1.0)
## Status
Draft

Back: [00_INDEX](00_INDEX.md)

## Global Definition of Done (DoD)
- Specs match implemented routes/DTOs/events exactly and do not introduce new requirements (../../AI_TASK_SPEC.md, ../../src/modules).
- Build/lint/test commands are defined and succeed in CI for the supported environment (../../package.json).

## Integrations Service v1.0 — DoD
### HTTP surface (paths + behavior)
- Endpoints exist and match exact paths (no `/api/v1` in the dedicated Integrations app) (src/modules/integrations/src/main.ts, src/modules/integrations/src/controllers/integrations.controller.ts).
- Outbound send:
  - Requires `Idempotency-Key` header and returns `400 MISSING_IDEMPOTENCY_KEY` when missing (src/modules/integrations/src/controllers/outbound-message.controller.ts).
  - Is idempotent for the same key + same payload and returns `409 IDEMPOTENCY_CONFLICT` for same key + different payload (src/modules/integrations/src/services/outbound-message.service.ts, src/modules/integrations/src/controllers/outbound-message.controller.ts, src/modules/integrations/src/services/idempotency.service.ts).
- Inbound webhooks:
  - Return `200 OK` with `OK` body on success (src/modules/integrations/src/controllers/inbound-webhook.controller.ts).
  - Inbound auth remains explicitly TBD; no signature/secret enforcement by default (src/modules/integrations/src/controllers/inbound-webhook.controller.ts, src/modules/integrations/src/config/integrations.config.ts).

### Events & broker abstraction
- Publishes events via a broker abstraction:
  - RabbitMQ publish supported when enabled (topic exchange `integrations.events`) (src/modules/integrations/src/services/event-publisher.service.ts, src/config/env.config.ts).
  - In-memory fallback is permitted only outside production; broker disabled in production fails fast (`BROKER_DISABLED_IN_PROD`) (src/modules/integrations/src/services/event-publisher.service.ts).

### Provider leakage boundary
- Provider-facing payload fields must not appear in internal DTOs/events consumed by other services (policy check; see leakage tests below) (src/modules/integrations/src/services/inbound-webhook.service.ts, src/modules/integrations/src/events/message-inbound-received.event.ts).

## Messages Service v1.0 — DoD
### HTTP surface
- Read endpoints exist and behave as documented (src/modules/messages/src/controllers/messages.controller.ts, src/main.ts).
- Query DTOs for `Conversation` and `Message` are stable and referenced by API contracts (src/modules/messages/src/dto/conversation.dto.ts, src/modules/messages/src/dto/message.dto.ts).

### Event consumption (at-least-once tolerance)
- Consumer-side deduplication exists and is applied to inbound message + status events (src/modules/messages/src/services/dedup.service.ts, src/modules/messages/src/services/message-processing.service.ts).
- Retry/DLQ strategy is defined and implemented for subscriber failures (currently marked TODO) (src/modules/messages/src/services/integration-event-subscriber.service.ts).

### Broker integration
- Production-grade broker consumption/publishing is implemented (RabbitMQ publish + consume with retry/DLQ) (src/modules/messages/src/services/message-event-publisher.service.ts, src/modules/messages/src/services/integration-event-subscriber.service.ts).

## Realtime Gateway v1.0 — DoD
- Socket.IO gateway exists and publishes `messages.created` and `messages.status.updated` to clients (src/modules/realtime/src/main.ts, src/modules/messages/src/events/*).
- Auth enforcement is configurable via `AUTH_REQUIRED` (src/modules/auth/src/middleware/auth.middleware.ts, src/modules/realtime/src/main.ts).

## Auth Service v1.0 — DoD
- Auth API exists (JWT/API-key) and is integrated with inbound requests when `AUTH_REQUIRED=true` (src/modules/auth/src/controllers/auth.controller.ts, src/modules/auth/src/middleware/auth.middleware.ts, src/main.ts, src/modules/messages/src/main.ts).

## Measurable checks (commands; not executed here)
### Build & lint
- `npm run build` (../../package.json)
- `npm run lint:check` (../../package.json)

### Tests
- `npm test` (runs Integrations integration test under local/test settings) (../../package.json, src/modules/integrations/test/integration.test.ts)

### Contract drift checks
- Verify documented paths exist in code:
  - `rg -n \"\\\"/integrations/whatsapp/\" src/modules/integrations/src/controllers` (src/modules/integrations/src/controllers/integrations.controller.ts)
  - `rg -n \"router\\.get\\('/conversations'\" src/modules/messages/src/controllers` (src/modules/messages/src/controllers/messages.controller.ts)

### Provider leakage checks (policy)
- Ensure provider-specific strings do not leak outside Integrations:
  - `rg -n \"evolution-api|baileys|providerPayload\" src/modules -g\"!src/modules/integrations/**\"` (src/modules/integrations/src/services/inbound-webhook.service.ts)
