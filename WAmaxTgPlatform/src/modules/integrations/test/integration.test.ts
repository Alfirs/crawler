import assert from 'assert';
import request from 'supertest';
import { app } from '../src/main';

async function run() {
  const health = await request(app).get('/health');
  assert.strictEqual(health.status, 200);
  assert.strictEqual(health.body.status, 'OK');
  assert.strictEqual(health.body.service, 'integrations');

  const testRequest = {
    channel: 'WHATSAPP',
    accountId: 'test-account',
    conversationRef: {
      type: 'EXTERNAL_PARTICIPANT',
      id: '1234567890@c.us'
    },
    message: {
      clientMessageId: 'test-msg-123',
      kind: 'TEXT',
      content: {
        text: 'Test message',
        format: 'PLAIN'
      }
    }
  };

  const outboundFirst = await request(app)
    .post('/integrations/whatsapp/outbound/send')
    .set('Idempotency-Key', 'test-key-123')
    .send(testRequest);

  assert.strictEqual(outboundFirst.status, 202);
  assert.ok(outboundFirst.body.deliveryRequestId);
  assert.ok(outboundFirst.body.status);

  const webhookPayload = {
    event: 'messages.upsert',
    instanceId: 'test-instance',
    key: {
      id: 'test-msg-id',
      remoteJid: '1234567890@c.us',
      fromMe: false
    },
    pushName: 'Test User',
    message: {
      conversation: 'Hello World'
    }
  };

  const webhook = await request(app)
    .post('/integrations/whatsapp/inbound/provider-webhook')
    .send(webhookPayload);

  assert.strictEqual(webhook.status, 200);

  const healthCheck = await request(app)
    .get('/integrations/whatsapp/channels/health?accountId=test-account');

  assert.strictEqual(healthCheck.status, 200);
  assert.strictEqual(healthCheck.body.channel, 'WHATSAPP');
  assert.strictEqual(healthCheck.body.accountId, 'test-account');
  assert.ok(healthCheck.body.connectionState);

  console.log('Integration tests passed');
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
