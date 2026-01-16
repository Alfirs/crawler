# WAmaxEdu — AI Context Pack (for Codex)

## 0) AI Governance
- Work strictly under AI_TASK_SPEC.md.
- Any changes only via change request.
- No invented requirements. Spec is source of truth.
- Evidence-based audit: file path + line numbers.

## 1) Product / Domain
Omnichannel platform (Wazzup-like):
WhatsApp/Telegram → unified inbox → CRM (Bitrix24 etc.)

System of Record:
- CRM = source of truth for clients/deals
- Platform = source of truth for messages/dialogs/status/events

## 2) Fixed Architecture (non-negotiable)
- Monorepo, microservices
- Node.js + Express
- Nuxt SSR (Vue), Socket.IO
- PostgreSQL, Redis
- RabbitMQ/Kafka
- Tarantool + Lua
- Kubernetes + CI/CD
Delivery:
- at-least-once, retries + DLQ, idempotency, status model
- No promise of 100% delivery to recipient

## 3) Strict Rules
- Integrations Service is the only provider-communication point
- Internal DTO/API are channel-agnostic
- Provider-specific fields MUST NOT leak (remoteJid, instanceId, upsert, etc.)
- Evolution API is reference only

## 4) Approved Specs
- Integrations Service v1.0 — APPROVED (path/to/spec or paste key endpoints/contracts)
- Messages Service v1.0 — APPROVED
- Realtime Gateway v1.0 — APPROVED
- Auth Service v1.0 — APPROVED
- E2E & Integration Test Plan v1.0 — APPROVED

## 5) Current Status
- Integrations Service implementation: in progress / verified (choose)
- Known checks: paths exact, idempotency Idempotency-Key + payload hash + 409 conflict, no leakage, broker abstraction, auth TBD.

## 6) Current Task (today)
- Verify / implement: <exact task here>
- Output format required: Self-audit PASS/FAIL with evidence + unified diffs only.
