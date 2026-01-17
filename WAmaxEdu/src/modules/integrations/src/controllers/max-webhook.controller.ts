import { Request, Response, Router } from 'express';
import { maxProvider } from '../services/providers/max-provider.service';
import { bitrix24Provider } from '../services/providers/bitrix24-provider.service';
import { logger } from '@/config/logger.config';
import { config } from '@/config/env.config';

/**
 * MAX Messenger Webhook Controller
 * Handles incoming events from MAX Platform
 */
export class MaxWebhookController {

    /**
     * Handle webhook from MAX
     */
    handleWebhook = async (req: Request, res: Response): Promise<void> => {
        try {
            // MAX might verify webhook existence via GET
            if (req.method === 'GET') {
                res.status(200).send(req.query.challenge || 'OK');
                return;
            }

            const payload = req.body;
            logger.info({ payload }, 'Received MAX webhook');

            // Handle incoming message
            // Hypothesis: event structure
            const eventType = payload.event || (payload.type === 'message_new' ? 'message_new' : 'unknown');
            const data = payload.data || payload.object || payload;

            if (eventType === 'message_new' || data.text) { // Soft check for message
                const chatId = data.chat_id || data.from_id;
                const userId = data.user_id || data.from_id;
                const text = data.text || data.body;
                const messageId = data.message_id || data.id || Date.now().toString();

                if (chatId && text) {
                    await bitrix24Provider.forwardExternalMessage({
                        externalChatId: chatId.toString(),
                        userName: data.from_user || 'MAX User',
                        message: text,
                        source: 'max'
                    });
                    logger.info({ chatId }, 'Forwarded MAX message to Bitrix24');
                }
            }

            res.status(200).json({ success: true });
        } catch (error) {
            logger.error({ err: error }, 'MaxWebhookController.handleWebhook error');
            res.status(500).json({ error: 'Internal server error' });
        }
    };

    /**
     * Setup webhook (register with MAX API)
     */
    setupWebhook = async (req: Request, res: Response): Promise<void> => {
        try {
            const result = await maxProvider.setWebhook();

            if (result) {
                res.status(200).json({ success: true, message: 'Webhook registered' });
            } else {
                res.status(500).json({ error: 'Failed to register webhook' });
            }
        } catch (error) {
            logger.error({ err: error }, 'Failed to setup MAX webhook');
            res.status(500).json({ error: 'Setup failed' });
        }
    };
}

// Create router
export function createMaxRouter(): Router {
    const router = Router();
    const controller = new MaxWebhookController();

    router.post('/webhook', controller.handleWebhook);
    router.get('/webhook', controller.handleWebhook); // Verify challenge
    router.post('/setup', controller.setupWebhook);

    return router;
}
