# Architecture (v1.0 Baseline)
## Status
Draft

Back: [00_INDEX](00_INDEX.md)

## Fixed baseline (governance)
- Monorepo: services + WebApp + infrastructure in one repository (../../AI_TASK_SPEC.md).
- Event/queue/realtime contracts are first-class and must be specified (Kafka/RabbitMQ/Socket.IO referenced as target technologies) (../../AI_TASK_SPEC.md).

## Fixed stack (verified in this repo snapshot)
- Node.js + Express for HTTP services (../../package.json, src/main.ts, src/modules/integrations/src/main.ts).
- PostgreSQL/MySQL as the relational database provider (configuration supports both) (src/config/env.config.ts, ../../env.example).
- Redis for caching/idempotency (src/config/redis.config.ts, src/config/env.config.ts, ../../env.example).
- RabbitMQ for event publishing (publisher implemented; consumer side TBD) (src/modules/integrations/src/services/event-publisher.service.ts, src/config/env.config.ts, ../../env.example).
- Kafka client dependency is present (`kafkajs`); usage/ownership is TBD in this repo snapshot (../../package.json).
- Socket.IO dependency is present; Realtime Gateway implementation is TBD in this repo snapshot (../../package.json).

## Fixed stack (TODO: not found in this repo snapshot)
- Nuxt SSR (Vue) WebApp: TODO: provide location within this monorepo (AI_TASK_SPEC says WebApp is included) (../../AI_TASK_SPEC.md).
- Tarantool + Lua: TODO: provide location/manifests and intended ownership boundaries (source not found in allowed repo artifacts).
- Kubernetes + CI/CD: TODO: provide manifests/pipelines for services/WebApp/infrastructure (source not found at repo root).

## Current repository snapshot (implemented)
- Runtime: Node.js + Express HTTP services (../../package.json, src/main.ts, src/modules/integrations/src/main.ts).
- Data access: Prisma client configured for a relational DB connection URI (src/config/database.config.ts, src/config/env.config.ts, ../../env.example).
- Redis: optional dependency used for idempotency storage (src/config/redis.config.ts, src/config/env.config.ts, src/modules/integrations/src/services/idempotency.service.ts).
- Broker: RabbitMQ publish support exists for Integrations events; fallback to in-memory emitter when broker disabled and not in production (src/modules/integrations/src/services/event-publisher.service.ts, src/config/env.config.ts).

## Services and responsibilities (Approved Services v1.0)
### Integrations Service
- Sole provider communication point (WhatsApp in v1.0): inbound provider webhooks + outbound send + channel connect/health (src/modules/integrations/src/controllers/integrations.controller.ts).
- Publishes normalized internal events (`messages.inbound.received`, `messages.delivery.status.updated`, `channels.connection.state.changed`) (src/modules/integrations/src/services/event-publisher.service.ts, src/modules/integrations/src/events/*).
- Idempotency for outbound send via `Idempotency-Key` and a TTL-based store (src/modules/integrations/src/controllers/outbound-message.controller.ts, src/modules/integrations/src/services/outbound-message.service.ts, src/modules/integrations/src/services/idempotency.service.ts).

### Messages Service
- Intended to consume Integrations events, deduplicate, persist conversations/messages, and expose query APIs (src/modules/messages/src/services/integration-event-subscriber.service.ts, src/modules/messages/src/services/message-processing.service.ts, src/modules/messages/src/controllers/messages.controller.ts).
- Provides read APIs for conversations/messages (src/modules/messages/src/controllers/messages.controller.ts).

### Realtime Gateway
- Socket.IO gateway pushes message/conversation updates to UI clients (src/modules/realtime/src/main.ts, src/modules/messages/src/events/*).

### Auth Service
- Auth API issues/verifies JWT or API keys and integrates with service inbound requests when enabled (src/modules/auth/src/controllers/auth.controller.ts, src/modules/auth/src/middleware/auth.middleware.ts).

## System of record boundaries
- CRM is the SoR for business/customer data; WAmaxEdu Platform is the SoR for messaging transport artifacts and delivery/read statuses (../../AI_TASK_SPEC.md).
- Messages domain objects in this repo: `Conversation`, `Message`, `MessageDeliveryState` (src/modules/messages/src/dto/conversation.dto.ts, src/modules/messages/src/dto/message.dto.ts, src/modules/messages/src/dto/delivery-status.dto.ts).

## Event-driven delivery model (at-least-once)
- Integrations publishes events to a broker abstraction (RabbitMQ topic exchange `integrations.events`) with persistent messages when enabled (src/modules/integrations/src/services/event-publisher.service.ts).
- Messages service implements consumer-side deduplication keyed by channel/account/external message reference to tolerate duplicates (src/modules/messages/src/services/dedup.service.ts, src/modules/messages/src/services/message-processing.service.ts).
- Retries and DLQ: not implemented; subscriber explicitly marks as TODO for retry/DLQ behavior (src/modules/messages/src/services/integration-event-subscriber.service.ts).

## Data stores (conceptual)
- PostgreSQL (or MySQL) is the configured primary DB provider (src/config/env.config.ts, ../../env.example).
- Redis is used for idempotency when enabled (src/modules/integrations/src/services/idempotency.service.ts, src/config/redis.config.ts).

## Security and authentication notes
- Inbound webhook auth is explicitly TBD; current implementation accepts all inbound requests and suggests securing via network/firewall (src/modules/integrations/src/controllers/inbound-webhook.controller.ts).
- `INTEGRATIONS_WEBHOOK_SECRET` exists in config but is not enforced by current code (src/modules/integrations/src/config/integrations.config.ts, src/config/env.config.ts, ../../env.example).

## TODO (missing architecture details to finalize)
- Confirm the production topology (microservices vs a single API gateway app) and the canonical base paths (only Integrations has a dedicated `src/modules/integrations/src/main.ts`; Messages/Auth/Realtime do not).
- Provide Kubernetes manifests / CI-CD pipeline definitions and service-to-service networking assumptions (source: infrastructure; none found at repo root).
- Define Kafka usage vs RabbitMQ usage (kafkajs is present as a dependency, but no usage found in `src/`) (../../package.json).
