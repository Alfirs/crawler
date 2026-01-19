import axios, { AxiosInstance, AxiosError } from 'axios';
import { logger } from '@/config/logger.config';
import { config } from '@/config/env.config';

/**
 * Bitrix24 Open Channels Provider Service
 * Handles communication with Bitrix24 REST API for Open Channels integration
 */
export class Bitrix24ProviderService {
    private client: AxiosInstance;
    private webhookUrl: string;
    private connectorId: string;
    private isConnectorRegistered: boolean = false;

    constructor() {
        this.webhookUrl = config.BITRIX24_WEBHOOK_URL || '';
        this.connectorId = config.BITRIX24_CONNECTOR_ID || 'wamaxedu_whatsapp';

        this.client = axios.create({
            timeout: 30000,
            headers: {
                'Content-Type': 'application/json',
            },
        });
    }

    /**
     * Call Bitrix24 REST API method
     */
    private async callMethod<T = any>(method: string, params: Record<string, any> = {}): Promise<T> {
        if (!this.webhookUrl) {
            throw new Error('BITRIX24_WEBHOOK_URL is not configured');
        }

        const url = `${this.webhookUrl}${method}`;

        try {
            const response = await this.client.post(url, params);

            if (response.data.error) {
                throw new Error(`Bitrix24 API Error: ${response.data.error_description || response.data.error}`);
            }

            return response.data.result;
        } catch (error) {
            if (error instanceof AxiosError) {
                logger.error({
                    method,
                    status: error.response?.status,
                    data: error.response?.data
                }, 'Bitrix24 API call failed');
            }
            throw error;
        }
    }

    /**
     * Register custom connector
     * Should be called once during setup
     */
    async registerConnector(connectorId: string, name: string): Promise<boolean> {
        try {
            await this.callMethod('imconnector.register', {
                ID: connectorId,
                NAME: name,
                ICON: {
                    DATA_IMAGE: '', // Base64 icon (optional)
                },
                PLACEMENT_HANDLER: '', // URL for iframe placement (optional)
            });

            logger.info({ connectorId }, 'Bitrix24 connector registered');
            return true;
        } catch (error: any) {
            // Connector might already be registered
            if (error.message?.includes('already registered') || error.message?.includes('ID_ALREADY_EXISTS')) {
                logger.info({ connectorId }, 'Bitrix24 connector already registered');
                return true;
            }
            logger.error({ err: error, connectorId }, 'Failed to register Bitrix24 connector');
            return false;
        }
    }

    /**
     * Activate connector for a specific Open Channel line
     */
    async activateConnector(connectorId: string, lineId: string): Promise<boolean> {
        try {
            await this.callMethod('imconnector.activate', {
                CONNECTOR: connectorId,
                LINE: lineId,
                ACTIVE: 1,
            });

            logger.info({ connectorId, lineId }, 'Bitrix24 connector activated');
            return true;
        } catch (error) {
            logger.error({ err: error, connectorId, lineId }, 'Failed to activate Bitrix24 connector');
            return false;
        }
    }

    /**
     * Send incoming message to Bitrix24 Open Channel
     * This creates a new chat or continues existing conversation
     */
    async sendMessageToOpenChannel(params: {
        connectorId?: string;
        lineId: string;
        externalChatId: string;      // WhatsApp/MAX chatId
        externalUserId: string;       // User ID
        externalUserName: string;     // Contact name
        messageId: string;            // External message ID
        messageText: string;          // Message content
        messageTimestamp: number;     // Unix timestamp
        files?: Array<{
            name: string;
            link: string;
            type: string;
        }>;
    }): Promise<{ chatId: number; messageId: number } | null> {
        const connector = params.connectorId || this.connectorId;
        try {
            const result = await this.callMethod('imconnector.send.messages', {
                CONNECTOR: connector,
                LINE: params.lineId,
                MESSAGES: [{
                    user: {
                        id: params.externalUserId,
                        name: params.externalUserName,
                        avatar: '',
                        url: `https://wa.me/${params.externalUserId.replace(/\D/g, '')}`, // TBD: Custom profile URL for MAX?
                    },
                    chat: {
                        id: params.externalChatId,
                        name: params.externalUserName,
                        url: `https://wa.me/${params.externalUserId.replace(/\D/g, '')}`,
                    },
                    message: {
                        id: params.messageId,
                        date: params.messageTimestamp,
                        text: params.messageText,
                        files: params.files || [],
                    },
                }],
            });

            logger.info({
                connector,
                externalChatId: params.externalChatId,
                messageId: params.messageId,
                result
            }, 'Message sent to Bitrix24 Open Channel');

            return result;
        } catch (error) {
            logger.error({ err: error, params }, 'Failed to send message to Bitrix24');
            return null;
        }
    }

    async updateMessageStatus(params: {
        connectorId?: string;
        lineId: string;
        externalChatId: string;
        messageIds: string[];
        status: 'delivered' | 'read';
    }): Promise<boolean> {
        const connector = params.connectorId || this.connectorId;
        try {
            await this.callMethod('imconnector.send.status.delivery', {
                CONNECTOR: connector,
                LINE: params.lineId,
                MESSAGES: params.messageIds.map(id => ({
                    im: { chat_id: params.externalChatId, message_id: id },
                    date: Math.floor(Date.now() / 1000),
                })),
            });

            logger.info({ params }, 'Message status updated in Bitrix24');
            return true;
        } catch (error) {
            logger.error({ err: error, params }, 'Failed to update message status in Bitrix24');
            return false;
        }
    }

    /**
     * Get list of Open Channel lines
     */
    async getOpenLines(): Promise<Array<{ id: string; name: string }>> {
        try {
            const result = await this.callMethod('imopenlines.config.list.get');
            return result || [];
        } catch (error) {
            logger.error({ err: error }, 'Failed to get Open Channel lines');
            return [];
        }
    }

    /**
     * Create a new lead in CRM from WhatsApp contact
     */
    async createLead(params: {
        name: string;
        phone: string;
        source?: string;
        comment?: string;
    }): Promise<number | null> {
        try {
            const result = await this.callMethod('crm.lead.add', {
                fields: {
                    TITLE: `WhatsApp: ${params.name}`,
                    NAME: params.name,
                    PHONE: [{ VALUE: params.phone, VALUE_TYPE: 'MOBILE' }],
                    SOURCE_ID: params.source || 'WEB',
                    COMMENTS: params.comment || 'Lead created from WhatsApp via WAmaxEdu',
                },
            });

            logger.info({ leadId: result, phone: params.phone }, 'CRM Lead created');
            return result;
        } catch (error) {
            logger.error({ err: error, params }, 'Failed to create CRM lead');
            return null;
        }
    }

    /**
     * Find contact by phone number
     */
    async findContactByPhone(phone: string): Promise<{ id: number; name: string } | null> {
        try {
            const result = await this.callMethod('crm.contact.list', {
                filter: { PHONE: phone },
                select: ['ID', 'NAME', 'LAST_NAME'],
            });

            if (result && result.length > 0) {
                const contact = result[0];
                return {
                    id: contact.ID,
                    name: `${contact.NAME || ''} ${contact.LAST_NAME || ''}`.trim(),
                };
            }

            return null;
        } catch (error) {
            logger.error({ err: error, phone }, 'Failed to find contact by phone');
            return null;
        }
    }

    /**
     * Check if webhook URL is configured
     */
    isConfigured(): boolean {
        return !!this.webhookUrl;
    }

    /**
     * Get connector ID
     */
    getConnectorId(): string {
        return this.connectorId;
    }

    // ============================================
    // WEBHOOK-COMPATIBLE METHODS (no OAuth needed)
    // ============================================

    /**
     * Store for external chat ID -> Bitrix chat ID mapping
     */
    private chatMapping: Map<string, number> = new Map();

    /**
     * Create or get existing chat for external user
     * Uses im.chat.add (works with webhooks)
     */
    async getOrCreateChat(params: {
        externalChatId: string;
        userName: string;
        source: 'whatsapp' | 'max';
    }): Promise<number | null> {
        // Check cache first
        const cached = this.chatMapping.get(params.externalChatId);
        if (cached) return cached;

        try {
            const chatId = await this.callMethod<number>('im.chat.add', {
                TYPE: 'OPEN',
                TITLE: `${params.source === 'whatsapp' ? 'WhatsApp' : 'MAX'}: ${params.userName}`,
                DESCRIPTION: `External ID: ${params.externalChatId}`,
                USERS: [], // Will be assigned to open line operators
            });

            this.chatMapping.set(params.externalChatId, chatId);
            logger.info({ externalChatId: params.externalChatId, bitrixChatId: chatId }, 'Created Bitrix chat');
            return chatId;
        } catch (error) {
            logger.error({ err: error, params }, 'Failed to create Bitrix chat');
            return null;
        }
    }

    /**
     * Send message to Bitrix chat
     * Uses im.message.add (works with webhooks)
     */
    async sendMessageToChat(params: {
        chatId: number;
        message: string;
        fromUser?: string;
    }): Promise<number | null> {
        try {
            const prefix = params.fromUser ? `[b]${params.fromUser}:[/b]\n` : '';
            const messageId = await this.callMethod<number>('im.message.add', {
                DIALOG_ID: `chat${params.chatId}`,
                MESSAGE: prefix + params.message,
                SYSTEM: 'Y', // Make message look system-generated (centered) to distinguish from outgoing
            });

            logger.info({ chatId: params.chatId, messageId }, 'Message sent to Bitrix');
            return messageId;
        } catch (error) {
            logger.error({ err: error, params }, 'Failed to send message to Bitrix');
            return null;
        }
    }

    /**
     * Simplified method: receive external message and forward to Bitrix
     */
    async forwardExternalMessage(params: {
        externalChatId: string;
        userName: string;
        message: string;
        source: 'whatsapp' | 'max';
        registerForPolling?: boolean;
    }): Promise<boolean> {
        const chatId = await this.getOrCreateChat({
            externalChatId: params.externalChatId,
            userName: params.userName,
            source: params.source,
        });

        if (!chatId) return false;

        const messageId = await this.sendMessageToChat({
            chatId,
            message: params.message,
            fromUser: params.userName,
        });

        // Register with poller for reverse flow (after sending, so we have messageId)
        if (params.registerForPolling !== false && messageId) {
            try {
                const { bitrix24Poller } = await import('./bitrix24-poller.service');
                bitrix24Poller.registerChat(chatId, params.externalChatId, params.source, messageId);
            } catch (e) {
                // Poller not available, skip
            }
        }

        return !!messageId;
    }

    /**
     * Get messages from a Bitrix chat (for polling)
     */
    async getChatMessages(chatId: number, lastMessageId: number = 0): Promise<Array<{
        id: number;
        text: string;
        author_id: number;
    }> | null> {
        try {
            const result = await this.callMethod<any>('im.dialog.messages.get', {
                DIALOG_ID: `chat${chatId}`,
                LAST_ID: lastMessageId,
                LIMIT: 20
            });

            if (!result?.messages) return null;

            // Filter only new messages from operators (author_id > 0 means real user)
            return result.messages
                .filter((m: any) => m.id > lastMessageId && m.author_id > 0)
                .map((m: any) => ({
                    id: m.id,
                    text: m.text || '',
                    author_id: m.author_id
                }));
        } catch (error) {
            logger.error({ err: error, chatId }, 'Failed to get chat messages');
            return null;
        }
    }
}

// Singleton instance
export const bitrix24Provider = new Bitrix24ProviderService();
