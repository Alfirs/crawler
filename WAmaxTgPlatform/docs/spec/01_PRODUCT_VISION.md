# Product Vision (v1.0)
## Status
Draft

Back: [00_INDEX](00_INDEX.md)

## Vision
WAmaxEdu Platform provides a normalized messaging layer that connects external channels (currently WhatsApp) to internal CRM workflows: Integrations ingests provider webhooks and sends outbound messages, then publishes internal, channel-agnostic events for downstream services like Messages to persist and query conversations/messages (../../package.json, src/modules/integrations/src/controllers/integrations.controller.ts, src/modules/integrations/src/services/event-publisher.service.ts, src/modules/messages/src/controllers/messages.controller.ts).

## Target users
- CRM operators/agents who need a unified inbox view of conversations and delivery/read status (../../AI_TASK_SPEC.md, src/modules/messages/src/controllers/messages.controller.ts, src/modules/messages/src/dto/message.dto.ts).
- Platform administrators who connect/manage channel accounts (src/modules/integrations/src/controllers/channel.controller.ts).

## Core value proposition
- Omnichannel inbox → CRM: normalize inbound/outbound messages and statuses into internal DTOs/events that the CRM can treat consistently across providers/channels (src/modules/integrations/src/events/message-inbound-received.event.ts, src/modules/integrations/src/events/message-delivery-status-updated.event.ts).

## System of record (SoR)
- CRM is the SoR for customer/participant domain data; WAmaxEdu Platform is the SoR for messaging transport artifacts (message events, delivery/read status, connection state) (../../AI_TASK_SPEC.md).

## Primary workflows (high level)
- Connect a WhatsApp account: client calls `POST /integrations/whatsapp/channels/connect` → Integrations publishes connection state events (src/modules/integrations/src/controllers/channel.controller.ts, src/modules/integrations/src/services/channel.service.ts, src/modules/integrations/src/events/channel-connection-state-changed.event.ts).
- Send outbound message: client calls `POST /integrations/whatsapp/outbound/send` with `Idempotency-Key` → Integrations sends via provider adapter and publishes delivery status events (src/modules/integrations/src/controllers/outbound-message.controller.ts, src/modules/integrations/src/services/outbound-message.service.ts, src/modules/integrations/src/services/providers/whatsapp-provider.service.ts, src/modules/integrations/src/events/message-delivery-status-updated.event.ts).
- Receive inbound message: provider calls `POST /integrations/whatsapp/inbound/provider-webhook` → Integrations normalizes payload into `MessageInboundReceived` and publishes it (src/modules/integrations/src/controllers/inbound-webhook.controller.ts, src/modules/integrations/src/services/inbound-webhook.service.ts, src/modules/integrations/src/events/message-inbound-received.event.ts).
- Persist and query: Messages service consumes Integrations events, deduplicates, then (intended) upserts conversations/messages and exposes query endpoints (src/modules/messages/src/services/integration-event-subscriber.service.ts, src/modules/messages/src/services/message-processing.service.ts, src/modules/messages/src/services/dedup.service.ts, src/modules/messages/src/controllers/messages.controller.ts).
- Realtime UI updates: publish message created/status events to a Realtime Gateway for UI subscriptions (planned; not implemented in this repo) (../../AI_TASK_SPEC.md, ../../package.json).

## TODO (missing info to finalize)
- Define target CRM(s) and the exact integration surface (API, events, DB sync) (source: product requirements; not present in repo).
- Define user roles/permissions and authentication model for external clients (source: Auth service spec; no implementation found under `src/modules/auth/src/**`).
- Confirm the intended public base paths for each microservice vs the current monolithic mount points (source: platform gateway/infrastructure; only `src/main.ts` and `src/modules/integrations/src/main.ts` exist).

