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
     * Register custom connector for WhatsApp
     * Should be called once during setup
     */
    async registerConnector(): Promise<boolean> {
        try {
            await this.callMethod('imconnector.register', {
                ID: this.connectorId,
                NAME: 'WAmaxEdu WhatsApp',
                ICON: {
                    DATA_IMAGE: '', // Base64 icon (optional)
                },
                PLACEMENT_HANDLER: '', // URL for iframe placement (optional)
            });

            logger.info({ connectorId: this.connectorId }, 'Bitrix24 connector registered');
            this.isConnectorRegistered = true;
            return true;
        } catch (error: any) {
            // Connector might already be registered
            if (error.message?.includes('already registered') || error.message?.includes('ID_ALREADY_EXISTS')) {
                logger.info({ connectorId: this.connectorId }, 'Bitrix24 connector already registered');
                this.isConnectorRegistered = true;
                return true;
            }
            logger.error({ err: error }, 'Failed to register Bitrix24 connector');
            return false;
        }
    }

    /**
     * Activate connector for a specific Open Channel line
     */
    async activateConnector(lineId: string): Promise<boolean> {
        try {
            await this.callMethod('imconnector.activate', {
                CONNECTOR: this.connectorId,
                LINE: lineId,
                ACTIVE: 1,
            });

            logger.info({ connectorId: this.connectorId, lineId }, 'Bitrix24 connector activated');
            return true;
        } catch (error) {
            logger.error({ err: error, lineId }, 'Failed to activate Bitrix24 connector');
            return false;
        }
    }

    /**
     * Send incoming WhatsApp message to Bitrix24 Open Channel
     * This creates a new chat or continues existing conversation
     */
    async sendMessageToOpenChannel(params: {
        lineId: string;
        externalChatId: string;      // WhatsApp JID (e.g., 79010535205@s.whatsapp.net)
        externalUserId: string;       // WhatsApp number
        externalUserName: string;     // Contact name from WhatsApp
        messageId: string;            // External message ID
        messageText: string;          // Message content
        messageTimestamp: number;     // Unix timestamp
        files?: Array<{
            name: string;
            link: string;
            type: string;
        }>;
    }): Promise<{ chatId: number; messageId: number } | null> {
        try {
            const result = await this.callMethod('imconnector.send.messages', {
                CONNECTOR: this.connectorId,
                LINE: params.lineId,
                MESSAGES: [{
                    user: {
                        id: params.externalUserId,
                        name: params.externalUserName,
                        avatar: '',
                        url: `https://wa.me/${params.externalUserId.replace(/\D/g, '')}`,
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

    /**
     * Update message status in Bitrix24 (delivered, read)
     */
    async updateMessageStatus(params: {
        lineId: string;
        externalChatId: string;
        messageIds: string[];
        status: 'delivered' | 'read';
    }): Promise<boolean> {
        try {
            await this.callMethod('imconnector.send.status.delivery', {
                CONNECTOR: this.connectorId,
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
}

// Singleton instance
export const bitrix24Provider = new Bitrix24ProviderService();
