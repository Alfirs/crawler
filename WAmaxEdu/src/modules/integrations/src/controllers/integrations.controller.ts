import { Router } from 'express';
import { OutboundMessageController } from './outbound-message.controller';
import { InboundWebhookController } from './inbound-webhook.controller';
import { ChannelController } from './channel.controller';
import { createBitrix24Router } from './bitrix24-webhook.controller';

export class IntegrationsController {
  private router: Router;

  constructor() {
    this.router = Router();

    // Initialize sub-controllers
    const outboundMessageController = new OutboundMessageController();
    const inboundWebhookController = new InboundWebhookController();
    const channelController = new ChannelController();
    const bitrix24Router = createBitrix24Router();

    // Routes
    this.router.post('/whatsapp/outbound/send', outboundMessageController.sendMessage);
    this.router.post('/whatsapp/inbound/provider-webhook', inboundWebhookController.handleWebhook);
    this.router.post('/whatsapp/inbound/provider-status', inboundWebhookController.handleStatus);
    this.router.post('/whatsapp/channels/connect', channelController.connect);
    this.router.post('/whatsapp/channels/disconnect', channelController.disconnect);
    this.router.get('/whatsapp/channels/health', channelController.health);

    // Bitrix24 Routes
    this.router.use('/bitrix24', bitrix24Router);
  }

  get routerInstance(): Router {
    return this.router;
  }
}

// Export router instance
export const integrationsRouter = new IntegrationsController().routerInstance;