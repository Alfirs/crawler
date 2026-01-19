# Non-Goals (v1.0)
## Status
Draft

Back: [00_INDEX](00_INDEX.md)

## Explicit non-goals
- No provider delivery guarantee: the platform does not promise 100% delivery or provider-side SLAs; delivery processing is at-least-once with idempotency/deduplication (src/modules/integrations/README.md, src/modules/messages/README.md, src/modules/messages/src/services/dedup.service.ts).
- No direct provider communication outside Integrations: all provider-facing endpoints/payloads must be isolated to Integrations (src/modules/integrations/src/controllers/integrations.controller.ts, src/modules/integrations/src/controllers/inbound-webhook.controller.ts).
- No provider-/channel-specific DTO leakage to internal services: internal APIs/events are intended to be channel-agnostic and must not expose provider-specific fields (policy; verify against internal DTOs/events such as `MessageInboundReceived`) (src/modules/integrations/src/events/message-inbound-received.event.ts).
- No tech stack changes via this spec work: changes to system design/tech stack are explicitly out of scope (../../AI_TASK_SPEC.md).

## Out of scope for v1.0 (TODO)
- Confirm whether non-approved modules (`notifications`, `reports`, `users`) are out of scope for v1.0 specs (source: product roadmap; only code folders exist at `src/modules/*`).
- Confirm whether multi-channel support beyond WhatsApp is in scope (Channel enum includes `TELEGRAM` but validations accept only `WHATSAPP`) (src/modules/integrations/src/types/enums.ts, src/modules/integrations/src/validate/outbound-message.schema.ts).

