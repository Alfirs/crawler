import { Request, Response, Router } from 'express';
import { bitrix24Provider } from '../services/providers/bitrix24-provider.service';
import { WhatsAppProviderService } from '../services/providers/whatsapp-provider.service';
import { maxProvider } from '../services/providers/max-provider.service';
import { logger } from '@/config/logger.config';
import { config } from '@/config/env.config';

/**
 * Bitrix24 Webhook Controller
 * Handles incoming events from Bitrix24 Open Channels
 */
export class Bitrix24WebhookController {
    private whatsappProvider: WhatsAppProviderService;

    constructor() {
        this.whatsappProvider = new WhatsAppProviderService();
    }

    /**
     * Handle webhook from Bitrix24
     * Called when operator sends message from Open Channel
     */
    handleWebhook = async (req: Request, res: Response): Promise<void> => {
        try {
            const payload = req.body;
            const event = payload.event || req.query.event;

            logger.info({ event, payload }, 'Received Bitrix24 webhook');

            switch (event) {
                case 'ONIMCONNECTORMESSAGEADD':
                    await this.handleOutgoingMessage(payload);
                    break;
                case 'ONIMCONNECTORSTATUSDELETE':
                    await this.handleConnectorDelete(payload);
                    break;
                case 'ONIMCONNECTORLINEDELETE':
                    await this.handleLineDelete(payload);
                    break;
                default:
                    logger.warn({ event }, 'Unknown Bitrix24 event');
            }

            res.status(200).json({ success: true });
        } catch (error) {
            logger.error({ err: error }, 'Bitrix24WebhookController.handleWebhook error');
            res.status(500).json({ error: 'Internal server error' });
        }
    };

    /**
     * Handle outgoing message from Bitrix24 operator
     * Send it to WhatsApp via Evolution API
     */
    private async handleOutgoingMessage(payload: any): Promise<void> {
        const data = payload.data || payload;

        // Extract message details from Bitrix24 webhook
        const connector = data.CONNECTOR;
        const lineId = data.LINE;
        const messages = data.MESSAGES || [];

        if (connector === config.BITRIX24_CONNECTOR_ID) {
            await this.sendToWhatsApp(messages, lineId);
        } else if (connector === config.BITRIX24_MAX_CONNECTOR_ID) {
            await this.sendToMax(messages, lineId);
        } else {
            logger.warn({ connector }, 'Message not for our configured connectors');
        }
    }

    private async sendToWhatsApp(messages: any[], lineId: string): Promise<void> {
        for (const msg of messages) {
            const chatId = msg.chat?.id;
            const messageText = msg.message?.text;
            const files = msg.message?.files || [];

            if (!chatId || !messageText) continue;

            // Format: 79010535205@s.whatsapp.net -> 79010535205
            const phoneNumber = chatId.replace('@s.whatsapp.net', '').replace('@c.us', '');

            try {
                const instanceName = config.EVOLUTION_INSTANCE_NAME || 'wamaxedu';

                await this.whatsappProvider.sendMessage({
                    instanceName,
                    to: phoneNumber,
                    type: 'text',
                    content: { text: messageText },
                });

                logger.info({ phoneNumber, messageText: messageText.substring(0, 50), lineId }, 'Sent to WhatsApp');

                for (const file of files) {
                    if (file.link) {
                        await this.whatsappProvider.sendMessage({
                            instanceName,
                            to: phoneNumber,
                            type: 'media',
                            content: {
                                mediaUrl: file.link,
                                caption: file.name || '',
                                mediaType: this.getMediaType(file.type),
                            },
                        });
                    }
                }
            } catch (error) {
                logger.error({ err: error, phoneNumber }, 'Failed to send to WhatsApp');
            }
        }
    }

    private async sendToMax(messages: any[], lineId: string): Promise<void> {
        for (const msg of messages) {
            const chatId = msg.chat?.id; // MAX chat ID
            const messageText = msg.message?.text;
            const files = msg.message?.files || []; // MAX attachments?

            if (!chatId || !messageText) continue;

            try {
                // TBD: Handle attachments for MAX
                const attachments = files.map((f: any) => ({
                    type: this.getMediaType(f.type),
                    url: f.link
                })).filter((a: any) => a.url);

                await maxProvider.sendMessage({
                    chatId,
                    text: messageText,
                    format: 'markdown', // Bitrix sends plain text, maybe convert?
                    attachments: attachments.length ? attachments : undefined
                });

                logger.info({ chatId, messageText: messageText.substring(0, 50), lineId }, 'Sent to MAX');

            } catch (error) {
                logger.error({ err: error, chatId }, 'Failed to send to MAX');
            }
        }
    }

    /**
     * Handle connector deletion event
     */
    private async handleConnectorDelete(payload: any): Promise<void> {
        logger.info({ payload }, 'Connector deleted in Bitrix24');
        // Could trigger re-registration or cleanup
    }

    /**
     * Handle Open Channel line deletion event
     */
    private async handleLineDelete(payload: any): Promise<void> {
        logger.info({ payload }, 'Open Channel line deleted in Bitrix24');
        // Could trigger cleanup
    }

    /**
     * Map file type to WhatsApp media type
     */
    private getMediaType(mimeType: string): 'image' | 'video' | 'audio' | 'document' {
        if (mimeType?.startsWith('image/')) return 'image';
        if (mimeType?.startsWith('video/')) return 'video';
        if (mimeType?.startsWith('audio/')) return 'audio';
        return 'document';
    }

    /**
     * Setup webhook endpoint (for initial configuration)
     */
    setupWebhook = async (req: Request, res: Response): Promise<void> => {
        try {
            // Register connectors
            const registeredWA = await bitrix24Provider.registerConnector(
                config.BITRIX24_CONNECTOR_ID,
                'WAmaxEdu WhatsApp'
            );

            const registeredMAX = await bitrix24Provider.registerConnector(
                config.BITRIX24_MAX_CONNECTOR_ID,
                'WAmaxEdu MAX'
            );

            if (!registeredWA && !registeredMAX) {
                res.status(500).json({ error: 'Failed to register connectors' });
                return;
            }

            // Get available Open Channel lines
            const lines = await bitrix24Provider.getOpenLines();

            res.status(200).json({
                success: true,
                success: true,
                connectors: [config.BITRIX24_CONNECTOR_ID, config.BITRIX24_MAX_CONNECTOR_ID],
                availableLines: lines,
                message: 'Connectors registered. Activate them for a specific Open Channel line.',
            });
        } catch (error) {
            logger.error({ err: error }, 'Failed to setup Bitrix24 webhook');
            res.status(500).json({ error: 'Setup failed' });
        }
    };

    /**
     * Activate connector for a specific Open Channel line
     */
    activateForLine = async (req: Request, res: Response): Promise<void> => {
        try {
            const { lineId } = req.body;

            if (!lineId) {
                res.status(400).json({ error: 'lineId is required' });
                return;
            }

            const activatedWA = await bitrix24Provider.activateConnector(config.BITRIX24_CONNECTOR_ID, lineId);
            const activatedMAX = await bitrix24Provider.activateConnector(config.BITRIX24_MAX_CONNECTOR_ID, lineId);

            if (!activatedWA && !activatedMAX) {
                res.status(500).json({ error: 'Failed to activate connectors for line' });
                return;
            }

            res.status(200).json({
                success: true,
                lineId,
                message: `Connector activated for Open Channel line ${lineId}`,
            });
        } catch (error) {
            logger.error({ err: error }, 'Failed to activate connector');
            res.status(500).json({ error: 'Activation failed' });
        }
    };
}

// Create router with controller
export function createBitrix24Router(): Router {
    const router = Router();
    const controller = new Bitrix24WebhookController();

    // Webhook endpoint (receives events from Bitrix24)
    router.post('/webhook', controller.handleWebhook);
    router.get('/webhook', controller.handleWebhook); // Bitrix24 sometimes sends GET

    // Setup and management endpoints
    router.post('/setup', controller.setupWebhook);
    router.post('/activate', controller.activateForLine);

    return router;
}
