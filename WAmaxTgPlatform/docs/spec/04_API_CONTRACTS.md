# API Contracts (v1.0)
## Status
Draft

Back: [00_INDEX](00_INDEX.md)

## Conventions (shared)
- Content type: JSON request/response bodies for all documented endpoints (src/main.ts, src/modules/integrations/src/main.ts).
- Error envelope (common shape):
  - `{"error":{"code":"...","message":"...","details":...}}` (src/modules/integrations/src/dto/response.dto.ts, src/main.ts, src/modules/integrations/src/main.ts).
- Unknown route: `404 NOT_FOUND` with error envelope (src/main.ts, src/modules/integrations/src/main.ts).

## Integrations Service (v1.0) — HTTP
### Base path notes
- Dedicated Integrations service app mounts router at `/integrations` and exposes `/health` (src/modules/integrations/src/main.ts).
- The monolithic app mounts the same router at `/api/v1/integrations` (src/main.ts); this contract documents the dedicated Integrations service paths (no `/api/v1`).

### Endpoints (exact paths)
| Method | Path | Purpose | Source |
|---|---|---|---|
| GET | `/health` | Service health check | src/modules/integrations/src/main.ts |
| POST | `/integrations/whatsapp/outbound/send` | Submit outbound message for delivery | src/modules/integrations/src/main.ts, src/modules/integrations/src/controllers/integrations.controller.ts, src/modules/integrations/src/controllers/outbound-message.controller.ts |
| POST | `/integrations/whatsapp/inbound/provider-webhook` | Inbound provider webhook (message) | src/modules/integrations/src/main.ts, src/modules/integrations/src/controllers/integrations.controller.ts, src/modules/integrations/src/controllers/inbound-webhook.controller.ts |
| POST | `/integrations/whatsapp/inbound/provider-status` | Inbound provider webhook (status) | src/modules/integrations/src/main.ts, src/modules/integrations/src/controllers/integrations.controller.ts, src/modules/integrations/src/controllers/inbound-webhook.controller.ts |
| POST | `/integrations/whatsapp/channels/connect` | Start WhatsApp account connection | src/modules/integrations/src/main.ts, src/modules/integrations/src/controllers/integrations.controller.ts, src/modules/integrations/src/controllers/channel.controller.ts |
| POST | `/integrations/whatsapp/channels/disconnect` | Disconnect WhatsApp account | src/modules/integrations/src/main.ts, src/modules/integrations/src/controllers/integrations.controller.ts, src/modules/integrations/src/controllers/channel.controller.ts |
| GET | `/integrations/whatsapp/channels/health?accountId=...` | WhatsApp connection health | src/modules/integrations/src/main.ts, src/modules/integrations/src/controllers/integrations.controller.ts, src/modules/integrations/src/controllers/channel.controller.ts |

### GET /health
- Response `200 OK`:
  - `{ status: "OK", timestamp: <ISO>, service: "integrations" }` (src/modules/integrations/src/main.ts).

### POST /integrations/whatsapp/outbound/send
#### Headers
- Required: `Idempotency-Key: <string>`; missing header returns `400 MISSING_IDEMPOTENCY_KEY` (src/modules/integrations/src/controllers/outbound-message.controller.ts).

#### Request DTO: OutboundMessageSendRequest
Source of truth: DTO + JSON schema (src/modules/integrations/src/dto/outbound-message-send.dto.ts, src/modules/integrations/src/dto/content.dto.ts, src/modules/integrations/src/types/enums.ts, src/modules/integrations/src/validate/outbound-message.schema.ts).

Top-level fields:
- `channel`: `Channel` (validated to `WHATSAPP` for this endpoint) (src/modules/integrations/src/validate/outbound-message.schema.ts).
- `accountId`: `string` (src/modules/integrations/src/dto/outbound-message-send.dto.ts).
- `conversationRef`: `{ type: ConversationType, id: string }` (src/modules/integrations/src/dto/outbound-message-send.dto.ts).
- `context?`: `{ replyToMessageId?: string, forwarded?: boolean, metadata?: Record<string, any> }` (src/modules/integrations/src/dto/outbound-message-send.dto.ts).
- `requestedAt?`: `string` (date-time in schema) (src/modules/integrations/src/validate/outbound-message.schema.ts).
- `message`: `{ clientMessageId: string, kind: MessageKind, content: ... }` (src/modules/integrations/src/dto/outbound-message-send.dto.ts).

`message.content` union (selected fields):
- `TextContent`: `{ text: string, format: TextFormat }` (src/modules/integrations/src/dto/content.dto.ts, src/modules/integrations/src/types/enums.ts).
- `MediaContent`: `{ mediaType: MediaType, source: { url?: string, fileId?: string }, caption?, filename?, mimeType?, sizeBytes?, thumbnail? }` (src/modules/integrations/src/dto/content.dto.ts, src/modules/integrations/src/types/enums.ts).
- `LocationContent`: `{ latitude: number, longitude: number, address?, title? }` (src/modules/integrations/src/dto/content.dto.ts).
- `ContactContent`: `{ contacts: Contact[] }` where `Contact` includes `displayName`, `phones[]`, optional `emails[]`, optional `organization` (src/modules/integrations/src/dto/content.dto.ts).
- `InteractiveContent`: `{ interactiveType: InteractiveType, bodyText: string, footerText?, actions: ... }` (src/modules/integrations/src/dto/content.dto.ts, src/modules/integrations/src/types/enums.ts).
- `ReactionContent`: `{ targetMessageId: string, reaction: string }` (src/modules/integrations/src/dto/content.dto.ts).

#### Response DTO: OutboundSendResponse
- Response `202 Accepted`: `{ deliveryRequestId: string, status: DeliveryStatus }` (src/modules/integrations/src/controllers/outbound-message.controller.ts, src/modules/integrations/src/dto/response.dto.ts).

#### Idempotency semantics
- Keyed by `Idempotency-Key` header; request body is hashed via stable stringify + SHA-256 (src/modules/integrations/src/services/outbound-message.service.ts, src/modules/integrations/src/services/idempotency.service.ts).
- Same key + different payload hash → `409 IDEMPOTENCY_CONFLICT` (src/modules/integrations/src/services/outbound-message.service.ts, src/modules/integrations/src/controllers/outbound-message.controller.ts).
- Storage:
  - Uses Redis `idempotency:<key>` when Redis is enabled and `IDEMPOTENCY_STORE !== "memory"` (src/modules/integrations/src/services/idempotency.service.ts, src/config/env.config.ts).
  - Falls back to in-memory store outside production; in-memory idempotency is rejected in production (`IDEMPOTENCY_MEMORY_NOT_ALLOWED_IN_PROD`) (src/modules/integrations/src/services/idempotency.service.ts).
- TTL seconds from `INTEGRATIONS_IDEMPOTENCY_TTL` (src/modules/integrations/src/config/integrations.config.ts, src/config/env.config.ts, ../../env.example).

### POST /integrations/whatsapp/inbound/provider-webhook
#### Behavior
- Accepts provider payload as JSON (`any`) and returns `200 OK` with body `OK` on success (src/modules/integrations/src/controllers/inbound-webhook.controller.ts).
- Current code does not enforce inbound auth; it is explicitly marked TBD and suggests network/firewall controls (src/modules/integrations/src/controllers/inbound-webhook.controller.ts).

#### Provider payload expectations (minimal fields used)
Provider payload is not schema-validated; the service reads the following fields when normalizing to an internal event (src/modules/integrations/src/services/inbound-webhook.service.ts):
- `instanceId` → internal `accountId` (fallback `"default"`) (src/modules/integrations/src/services/inbound-webhook.service.ts).
- `key.id`, `key.remoteJid`, `key.fromMe`, `key.participant` (src/modules/integrations/src/services/inbound-webhook.service.ts).
- `pushName` (sender display name) (src/modules/integrations/src/services/inbound-webhook.service.ts).
- `message.*` for message kind/content mapping (src/modules/integrations/src/services/inbound-webhook.service.ts).

#### Response codes
- `200 OK`: accepted and normalized (src/modules/integrations/src/controllers/inbound-webhook.controller.ts).
- `400 INVALID_PROVIDER_PAYLOAD`: normalization failed (src/modules/integrations/src/controllers/inbound-webhook.controller.ts, src/modules/integrations/src/services/inbound-webhook.service.ts).
- `401 INVALID_SIGNATURE`: handler exists but signature verification is not implemented (src/modules/integrations/src/controllers/inbound-webhook.controller.ts).

### POST /integrations/whatsapp/inbound/provider-status
#### Behavior
- Accepts provider payload as JSON (`any`) and returns `200 OK` with body `OK` on success (src/modules/integrations/src/controllers/inbound-webhook.controller.ts).
- Normalizes status to `DeliveryStatus` via `mapProviderStatus()` (src/modules/integrations/src/services/inbound-webhook.service.ts, src/modules/integrations/src/types/enums.ts).

#### Provider payload expectations (minimal fields used)
Fields read during normalization (src/modules/integrations/src/services/inbound-webhook.service.ts):
- `instanceId` → internal `accountId` (fallback `"default"`).
- `key.id` → internal `externalMessageRef.id`.
- `status` → internal `DeliveryStatus`.
- `error? { code, message }` → internal `reason? { code, message }`.

#### Response codes
- `200 OK`: accepted and normalized (src/modules/integrations/src/controllers/inbound-webhook.controller.ts).
- `400 INVALID_PROVIDER_PAYLOAD` (src/modules/integrations/src/controllers/inbound-webhook.controller.ts).
- `401 INVALID_SIGNATURE`: handler exists but signature verification is not implemented (src/modules/integrations/src/controllers/inbound-webhook.controller.ts).

### POST /integrations/whatsapp/channels/connect
#### Request DTO: ChannelConnectRequest
- `{ channel: Channel, accountId: string, mode: "NEW", metadata?: Record<string, any> }` (src/modules/integrations/src/dto/channel.dto.ts, src/modules/integrations/src/validate/channel.schema.ts).

#### Response DTO: ChannelConnectResponse
- `202 Accepted`: `{ connectRequestId: string, state: string }` (src/modules/integrations/src/controllers/channel.controller.ts, src/modules/integrations/src/dto/response.dto.ts).

### POST /integrations/whatsapp/channels/disconnect
#### Request DTO: ChannelDisconnectRequest
- `{ channel: Channel, accountId: string, reason: string }` (src/modules/integrations/src/dto/channel.dto.ts, src/modules/integrations/src/validate/channel.schema.ts).

#### Response DTO: ChannelDisconnectResponse
- `202 Accepted`: `{ state: "PENDING" }` (src/modules/integrations/src/controllers/channel.controller.ts, src/modules/integrations/src/dto/response.dto.ts).

### GET /integrations/whatsapp/channels/health?accountId=...
#### Query
- Required: `accountId` (src/modules/integrations/src/controllers/channel.controller.ts).

#### Response DTO: ChannelHealthResponse
- `200 OK`: `{ channel: string, accountId: string, connectionState: string, lastSeenAt: string, details: Record<string, any> }` (src/modules/integrations/src/controllers/channel.controller.ts, src/modules/integrations/src/dto/response.dto.ts).

### Error codes (Integrations HTTP)
Codes observed in controllers/middleware (source files in parentheses):
- `400 VALIDATION_ERROR` (schema validation) (src/modules/integrations/src/middleware/validation.middleware.ts).
- `400 MISSING_IDEMPOTENCY_KEY` (src/modules/integrations/src/controllers/outbound-message.controller.ts).
- `400 MISSING_ACCOUNT_ID` (src/modules/integrations/src/controllers/channel.controller.ts).
- `401 INVALID_SIGNATURE` (handler only; verification not implemented) (src/modules/integrations/src/controllers/inbound-webhook.controller.ts).
- `404 CHANNEL_ACCOUNT_NOT_FOUND` (src/modules/integrations/src/controllers/outbound-message.controller.ts, src/modules/integrations/src/controllers/channel.controller.ts).
- `409 IDEMPOTENCY_CONFLICT` (src/modules/integrations/src/controllers/outbound-message.controller.ts, src/modules/integrations/src/services/outbound-message.service.ts).
- `409 ALREADY_CONNECTED`, `409 CONNECT_IN_PROGRESS` (mapped in controller; not thrown by current service implementation) (src/modules/integrations/src/controllers/channel.controller.ts, src/modules/integrations/src/services/channel.service.ts).
- `422 UNSUPPORTED_CHANNEL`, `422 UNSUPPORTED_CONNECT_MODE`, `422 UNSUPPORTED_MESSAGE_TYPE` (src/modules/integrations/src/controllers/outbound-message.controller.ts, src/modules/integrations/src/controllers/channel.controller.ts).
- `500 INTERNAL_ERROR` (src/modules/integrations/src/controllers/*.ts, src/modules/integrations/src/main.ts).

## Integrations Service (v1.0) — Events
### Provider leakage rule (hard boundary)
- Provider payloads are accepted only at `/integrations/whatsapp/inbound/*` endpoints; downstream services should consume only normalized internal event contracts (src/modules/integrations/src/controllers/inbound-webhook.controller.ts, src/modules/integrations/src/services/inbound-webhook.service.ts).
- Internal events currently include optional `rawProviderRef` with a `provider` string and `payloadHash`; confirm whether this violates the “no provider-specific field leakage” policy (src/modules/integrations/src/events/message-inbound-received.event.ts, src/modules/integrations/src/services/inbound-webhook.service.ts).

### Transport/broker details
- Exchange: `integrations.events` (topic) (src/modules/integrations/src/services/event-publisher.service.ts).
- Routing keys (event names):
  - `messages.inbound.received`
  - `messages.delivery.status.updated`
  - `channels.connection.state.changed` (src/modules/integrations/src/services/event-publisher.service.ts).

Broker behavior:
- When `RABBITMQ_ENABLED=true`, publisher connects to `RABBITMQ_URI` and publishes persistent JSON messages (src/modules/integrations/src/services/event-publisher.service.ts, src/config/env.config.ts).
- When broker is disabled and `NODE_ENV !== "production"`, events are emitted in-memory for local/test; broker disabled in production throws `BROKER_DISABLED_IN_PROD` (src/modules/integrations/src/services/event-publisher.service.ts, src/config/env.config.ts).

### Event contract: messages.inbound.received (MessageInboundReceived)
Field list (source of truth: interface) (src/modules/integrations/src/events/message-inbound-received.event.ts, src/modules/integrations/src/events/base.event.ts, src/modules/integrations/src/events/types.ts):
- `eventId: string`, `occurredAt: string`
- `channel: Channel`, `accountId: string`
- `conversationRef: { type: ConversationType, id: string }`
- `externalMessageRef: { id: string, scope?: string }`
- `sender: { participantRef: { type: ParticipantType, id: string }, displayName?: string }`
- `message: { kind: MessageKind, content: MessageContent, context?: { replyToExternalMessageRef?: { id: string }, quotedText?: string } }`
- `rawProviderRef?: { provider: string, payloadHash?: string }`

### Event contract: messages.delivery.status.updated (MessageDeliveryStatusUpdated)
Field list (src/modules/integrations/src/events/message-delivery-status-updated.event.ts, src/modules/integrations/src/events/base.event.ts):
- `eventId: string`, `occurredAt: string`
- `channel: Channel`, `accountId: string`
- `deliveryRequestId?: string`, `clientMessageId?: string`
- `externalMessageRef: { id: string }`
- `status: DeliveryStatus`
- `reason?: { code: string, message?: string }`
- `isFinal: boolean`

### Event contract: channels.connection.state.changed (ChannelConnectionStateChanged)
Field list (src/modules/integrations/src/events/channel-connection-state-changed.event.ts, src/modules/integrations/src/events/base.event.ts):
- `eventId: string`, `occurredAt: string`
- `channel: Channel`, `accountId: string`
- `connectRequestId: string`
- `state: "PENDING" | "AWAITING_USER_ACTION" | "CONNECTED" | "DISCONNECTED" | "FAILED"`
- `details?: Record<string, any>`

## Messages Service (v1.0) — HTTP
### Base path notes
- `messagesRouter` defines routes relative to its mount point (src/modules/messages/src/controllers/messages.controller.ts).
- Current monolithic app mounts it at `/api/v1/messages` (src/main.ts).
- Dedicated Messages service app mounts router at `/messages` and exposes `/health` (src/modules/messages/src/main.ts).

### Endpoints (router-relative)
| Method | Path | Purpose | Source |
|---|---|---|---|
| GET | `/conversations?accountId=...&channel=...&limit?&offset?` | List conversations | src/modules/messages/src/controllers/messages.controller.ts |
| GET | `/conversations/:conversationId/messages?limit?&offset?&direction?` | List messages in conversation | src/modules/messages/src/controllers/messages.controller.ts |
| GET | `/messages/:messageId` | Fetch message by id | src/modules/messages/src/controllers/messages.controller.ts |

### Response DTOs (Messages)
- Conversation: `{ conversationId, channel, accountId, conversationRef, createdAt, updatedAt }` (src/modules/messages/src/dto/conversation.dto.ts).
- Message: `{ messageId, conversationId, direction, clientMessageId?, externalMessageRef?, kind, content, sender, occurredAt, createdAt }` (src/modules/messages/src/dto/message.dto.ts).
- Delivery state (internal model): `{ messageId, status, isFinal, reason?, updatedAt }` (src/modules/messages/src/dto/delivery-status.dto.ts).

### Error codes (Messages HTTP)
- `400 MISSING_PARAMETERS` when `accountId` or `channel` is missing on `/conversations` (src/modules/messages/src/controllers/messages.controller.ts).
- `404 MESSAGE_NOT_FOUND` on `/messages/:messageId` (src/modules/messages/src/controllers/messages.controller.ts).
- `500 INTERNAL_ERROR` on failures (src/modules/messages/src/controllers/messages.controller.ts).

## Messages Service (v1.0) — Events
### Consumed from Integrations
- Subscribes to:
  - `messages.inbound.received`
  - `messages.delivery.status.updated` (src/modules/messages/src/services/integration-event-subscriber.service.ts).
- Consumer-side dedup keys:
  - Inbound messages: `msg:<channel>:<accountId>:<externalMessageRefId>`
  - Status updates: `status:<channel>:<accountId>:<externalMessageRefId>:<status>:<occurredAt>` (src/modules/messages/src/services/dedup.service.ts).

### Published by Messages (in-memory)
Published via in-memory `EventEmitter2` (not broker-backed) (src/modules/messages/src/services/message-event-publisher.service.ts):
- Event name: `messages.created` with payload `MessageCreated` (src/modules/messages/src/events/message-created.event.ts).
- Event name: `messages.status.updated` with payload `MessageStatusUpdated` (src/modules/messages/src/events/status-updated.event.ts).

## Auth Service (v1.0) — HTTP
### Base path notes
- Dedicated Auth service app mounts router at `/auth` and exposes `/health` (src/modules/auth/src/main.ts).
- The monolithic app mounts the same router at `/api/v1/auth` (src/main.ts).

### Endpoints (exact paths)
| Method | Path | Purpose | Source |
|---|---|---|---|
| GET | `/health` | Service health check | src/modules/auth/src/main.ts |
| POST | `/auth/token` | Issue JWT from API key | src/modules/auth/src/main.ts, src/modules/auth/src/controllers/auth.controller.ts |
| POST | `/auth/verify` | Verify JWT or API key | src/modules/auth/src/main.ts, src/modules/auth/src/controllers/auth.controller.ts |

### POST /auth/token
#### Request
- `{ apiKey: string }`

#### Response
- `200 OK`: `{ token: string, expiresIn: number }`
- `400 MISSING_API_KEY`
- `401 INVALID_API_KEY`

### POST /auth/verify
#### Request
- Accepts `Authorization: Bearer <token>`, or `x-api-key`, or body `{ token?: string, apiKey?: string }`

#### Response
- `200 OK`: `{ valid: true, subject?: string }`
- `401 UNAUTHORIZED`

### Auth enforcement (shared)
- Auth is optional by default; when `AUTH_REQUIRED=true`, services enforce JWT/API-key verification (src/modules/auth/src/middleware/auth.middleware.ts, src/config/env.config.ts, src/main.ts, src/modules/messages/src/main.ts).

## Realtime Gateway (v1.0) — Socket.IO
### Base path notes
- Dedicated Realtime Gateway app exposes `/health` and Socket.IO server at the same host/port (src/modules/realtime/src/main.ts).

### Socket events
- `messages.created` (payload: MessageCreated) (src/modules/messages/src/events/message-created.event.ts, src/modules/realtime/src/main.ts).
- `messages.status.updated` (payload: MessageStatusUpdated) (src/modules/messages/src/events/status-updated.event.ts, src/modules/realtime/src/main.ts).

### Auth model
- When `AUTH_REQUIRED=true`, connections must provide a valid JWT or API key via `Authorization` header, `auth.token`, or `auth.apiKey` (src/modules/auth/src/middleware/auth.middleware.ts, src/modules/realtime/src/main.ts).

### Routing
- If `accountId` is provided in the handshake, the client is joined to `account:<accountId>` and events are emitted to that room (src/modules/realtime/src/main.ts).

## TODO (missing contract details)
- Confirm whether the canonical public paths include `/api/v1/*` (gateway) or service-local base paths like `/integrations/*` (only Integrations has both patterns implemented) (src/main.ts, src/modules/integrations/src/main.ts).
- Define provider signature verification: which headers, algorithm, and failure codes (current code contains `INVALID_SIGNATURE` handling but no verification) (src/modules/integrations/src/controllers/inbound-webhook.controller.ts, src/modules/integrations/src/config/integrations.config.ts).
- Provide a formal provider payload contract for inbound webhooks (current payload is `any`) (src/modules/integrations/src/services/inbound-webhook.service.ts).
- Confirm provider leakage policy for `rawProviderRef` (allowed vs forbidden) (src/modules/integrations/src/events/message-inbound-received.event.ts).
