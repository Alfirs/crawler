# Evolution API Integration Runbook

## 1) Start Evolution API (provider)
```
cd evolution-api-main
npm install
npm run dev
```

## 2) Configure WAmaxEdu Integrations Service
Set env vars (example):
```
WHATSAPP_PROVIDER_BASE_URL=http://localhost:8080
WHATSAPP_PROVIDER_API_KEY=your-provider-api-key
WHATSAPP_PROVIDER_WEBHOOK_URL=http://localhost:3001/integrations/whatsapp/inbound/provider-webhook
WHATSAPP_PROVIDER_WEBHOOK_EVENTS=messages.upsert,send.message.update
WHATSAPP_PROVIDER_WEBHOOK_BY_EVENTS=false
```

## 3) Start Integrations Service
```
npm run start:integrations
```

## 4) Connect WhatsApp instance (creates provider instance + webhook)
```
Invoke-RestMethod -Method Post -Uri http://localhost:3001/integrations/whatsapp/channels/connect -ContentType 'application/json' -Body '{
  "channel": "WHATSAPP",
  "accountId": "demo-account",
  "mode": "NEW"
}'
```

## 5) Send a test message
```
Invoke-RestMethod -Method Post -Uri http://localhost:3001/integrations/whatsapp/outbound/send -Headers @{ "Idempotency-Key" = "demo-1" } -ContentType 'application/json' -Body '{
  "channel": "WHATSAPP",
  "accountId": "demo-account",
  "conversationRef": { "type": "EXTERNAL_PARTICIPANT", "id": "1234567890" },
  "message": {
    "clientMessageId": "msg-1",
    "kind": "TEXT",
    "content": { "text": "Hello from WAmaxEdu", "format": "PLAIN" }
  }
}'
```

## 6) Receive inbound messages
Evolution API should push `messages.upsert` events to the webhook URL.
Inbound messages will be normalized and published as `messages.inbound.received`.
