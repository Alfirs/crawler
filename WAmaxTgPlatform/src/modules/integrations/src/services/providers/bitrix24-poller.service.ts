import { bitrix24Provider } from './bitrix24-provider.service';
import { WhatsAppProviderService } from './whatsapp-provider.service';
import { maxProvider } from './max-provider.service';
import { logger } from '@/config/logger.config';
import { config } from '@/config/env.config';

/**
 * Bitrix24 Message Poller
 * Polls Bitrix24 for operator messages and forwards them to WhatsApp/MAX
 */
export class Bitrix24PollerService {
    private whatsappProvider: WhatsAppProviderService;
    private pollingInterval: NodeJS.Timeout | null = null;
    private lastMessageIds: Map<number, number> = new Map(); // chatId -> lastMessageId
    private chatToExternal: Map<number, { externalId: string; source: 'whatsapp' | 'max' }> = new Map();

    constructor() {
        this.whatsappProvider = new WhatsAppProviderService();
    }

    /**
     * Register external chat mapping (called when we create a Bitrix chat)
     * Also sets initial lastMessageId to skip existing messages
     */
    registerChat(bitrixChatId: number, externalId: string, source: 'whatsapp' | 'max', lastMessageId?: number) {
        this.chatToExternal.set(bitrixChatId, { externalId, source });
        // Set initial message ID to avoid forwarding messages we just sent
        if (lastMessageId) {
            this.lastMessageIds.set(bitrixChatId, lastMessageId);
        } else {
            // Set a high initial value - will be corrected on first poll
            this.lastMessageIds.set(bitrixChatId, Date.now());
        }
        logger.info({ bitrixChatId, externalId, source, lastMessageId }, 'Registered chat mapping for polling');
    }

    /**
     * Start polling for new messages
     */
    start(intervalMs: number = 5000) {
        if (this.pollingInterval) {
            logger.warn('Poller already running');
            return;
        }

        logger.info({ intervalMs }, 'Starting Bitrix24 message poller');

        this.pollingInterval = setInterval(async () => {
            await this.pollMessages();
        }, intervalMs);
    }

    /**
     * Stop polling
     */
    stop() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
            logger.info('Stopped Bitrix24 message poller');
        }
    }

    /**
     * Poll for new messages in all registered chats
     */
    private async pollMessages() {
        for (const [bitrixChatId, mapping] of this.chatToExternal.entries()) {
            try {
                const lastId = this.lastMessageIds.get(bitrixChatId) || 0;

                // Get recent messages from chat
                const messages = await bitrix24Provider.getChatMessages(bitrixChatId, lastId);

                if (messages && messages.length > 0) {
                    for (const msg of messages) {
                        // Skip messages from external users (only forward operator messages)
                        if (msg.author_id === 0) continue; // System or external

                        await this.forwardMessage(mapping, msg);

                        // Update last message ID
                        if (msg.id > lastId) {
                            this.lastMessageIds.set(bitrixChatId, msg.id);
                        }
                    }
                }
            } catch (error) {
                logger.error({ err: error, bitrixChatId }, 'Error polling chat');
            }
        }
    }

    /**
     * Forward operator message to external platform
     */
    private async forwardMessage(
        mapping: { externalId: string; source: 'whatsapp' | 'max' },
        message: { id: number; text: string; author_id: number }
    ) {
        const { externalId, source } = mapping;
        const text = message.text;

        if (source === 'whatsapp') {
            // Extract phone from JID
            const phone = externalId.replace('@s.whatsapp.net', '').replace('@c.us', '');

            await this.whatsappProvider.sendMessage({
                instanceName: config.EVOLUTION_INSTANCE_NAME || 'wamaxedu',
                to: phone,
                type: 'text',
                content: { text }
            });

            logger.info({ phone, messageId: message.id }, 'Forwarded operator message to WhatsApp');
        } else if (source === 'max') {
            await maxProvider.sendMessage({
                chatId: externalId,
                text,
                format: 'markdown'
            });

            logger.info({ chatId: externalId, messageId: message.id }, 'Forwarded operator message to MAX');
        }
    }
}

// Singleton
export const bitrix24Poller = new Bitrix24PollerService();
