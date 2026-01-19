# WAmaxEdu Specifications (Source of Truth)
## Status
Draft

## Governance
- This spec set is governed by `AI_TASK_SPEC.md` ([AI_TASK_SPEC.md](../../AI_TASK_SPEC.md)).
- Evolution API is reference-only and must not be treated as authoritative requirements (../../AI_TASK_SPEC.md).

## Spec Set
- [01_PRODUCT_VISION](01_PRODUCT_VISION.md)
- [02_NON_GOALS](02_NON_GOALS.md)
- [03_ARCHITECTURE](03_ARCHITECTURE.md)
- [04_API_CONTRACTS](04_API_CONTRACTS.md)
- [05_ACCEPTANCE_CRITERIA](05_ACCEPTANCE_CRITERIA.md)
- [06_TEST_PLAN](06_TEST_PLAN.md)

## Approved Services v1.0
- Integrations
- Messages
- Realtime Gateway
- Auth

## Cross-cutting constraints (v1.0)
- Delivery semantics: at-least-once processing is assumed; retries + DLQ are required at the platform level; no 100% delivery guarantee (src/modules/integrations/README.md, src/modules/messages/src/services/integration-event-subscriber.service.ts).
- Idempotency:
  - Outbound send requires `Idempotency-Key` and must be idempotent for same key + same payload (`src/modules/integrations/src/controllers/outbound-message.controller.ts`, `src/modules/integrations/src/services/outbound-message.service.ts`, `src/modules/integrations/src/services/idempotency.service.ts`).
  - Event consumers must deduplicate events to tolerate at-least-once delivery (`src/modules/messages/src/services/dedup.service.ts`, `src/modules/messages/src/services/message-processing.service.ts`).
- Provider leakage ban: provider-specific fields/payloads must not leak beyond Integrations; other services must consume normalized internal DTOs/events only (src/modules/integrations/src/controllers/inbound-webhook.controller.ts, src/modules/integrations/src/services/inbound-webhook.service.ts).
- Status model: `PENDING | SENT | DELIVERED | READ | FAILED` (`src/modules/integrations/src/types/enums.ts`, `src/modules/messages/src/types/enums.ts`).

## Authoritative inputs (for this spec set)
- Governance/process: `AI_TASK_SPEC.md` (../../AI_TASK_SPEC.md).
- Runtime/config: `package.json`, `env.example` (../../package.json, ../../env.example).
- Implemented routes/DTOs/events: `src/modules/**` (../../src/modules).
