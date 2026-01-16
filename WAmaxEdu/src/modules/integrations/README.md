# Integrations Service v1.0

WhatsApp channel adapter for WAmaxEdu platform.

## Quick Start

```bash
# Install dependencies
npm install

# Development mode
npm run dev

# Production build
npm run build
npm run start:prod
```

## Environment Variables

```bash
PORT=3001
INTEGRATIONS_IDEMPOTENCY_TTL=86400
INTEGRATIONS_WEBHOOK_SECRET=your-secret
```

## API Endpoints

### Outbound Messages
- `POST /integrations/whatsapp/outbound/send` - Send message
- Headers: `Idempotency-Key`, `Authorization`

### Inbound Webhooks
- `POST /integrations/whatsapp/inbound/provider-webhook` - Receive messages
- `POST /integrations/whatsapp/inbound/provider-status` - Receive status updates

### Channel Management
- `POST /integrations/whatsapp/channels/connect` - Connect channel
- `POST /integrations/whatsapp/channels/disconnect` - Disconnect channel
- `GET /integrations/whatsapp/channels/health` - Check health

## Events Published

- `MessageInboundReceived` - New inbound messages
- `MessageDeliveryStatusUpdated` - Status updates
- `ChannelConnectionStateChanged` - Connection state changes

## Testing

```bash
npm test
```

## Architecture Notes

- At-least-once delivery semantics
- Idempotency via TTL-based caching
- Event publishing via broker abstraction
- Provider payload normalization
- Status model: PENDING → SENT → DELIVERED → READ | FAILED
