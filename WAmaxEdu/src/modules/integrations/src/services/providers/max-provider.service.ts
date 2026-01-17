import axios, { AxiosInstance, AxiosError } from 'axios';
import { logger } from '@/config/logger.config';
import { config } from '@/config/env.config';

/**
 * MAX Messenger Provider Service
 * Handles communication with MAX Messenger API
 */
export class MaxProviderService {
    private client: AxiosInstance;
    private token: string;
    private apiUrl: string;
    private webhookUrl: string;

    constructor() {
        this.token = config.MAX_BOT_TOKEN || '';
        this.apiUrl = config.MAX_API_URL || 'https://platform-api.max.ru';
        this.webhookUrl = config.MAX_WEBHOOK_URL || '';

        this.client = axios.create({
            baseURL: this.apiUrl,
            timeout: 30000,
            headers: {
                'Content-Type': 'application/json',
            },
        });

        // Add auth interceptor
        this.client.interceptors.request.use((req) => {
            if (this.token) {
                req.headers['Authorization'] = this.token;
            }
            return req;
        });
    }

    /**
     * Check if provider is configured
     */
    isConfigured(): boolean {
        return !!this.token;
    }

    /**
     * Set webhook for bot events
     */
    async setWebhook(): Promise<boolean> {
        if (!this.webhookUrl) {
            logger.warn('MAX_WEBHOOK_URL not configured');
            return false;
        }

        try {
            await this.client.post('/subscriptions', {
                url: this.webhookUrl,
            });

            logger.info({ url: this.webhookUrl }, 'MAX webhook configured');
            return true;
        } catch (error) {
            this.logError('setWebhook', error);
            return false;
        }
    }

    /**
     * Send text message to user or chat
     */
    async sendMessage(params: {
        chatId?: string; // or userId
        userId?: string;
        text: string;
        format?: 'markdown' | 'html';
        attachments?: Array<{
            type: string; // TBD: confirm MAX attachment structure
            url: string;
        }>;
    }): Promise<{ message_id: string } | null> {
        try {
            const payload: any = {
                text: params.text,
                format: params.format || 'markdown',
                notify: true,
            };

            if (params.chatId) payload.chat_id = params.chatId;
            if (params.userId) payload.user_id = params.userId;

            // Note: Attachments structure needs verification against MAX API docs
            // Assuming array of objects based on initial doc review
            if (params.attachments && params.attachments.length > 0) {
                payload.attachments = params.attachments;
            }

            const response = await this.client.post('/messages', payload);

            logger.info({
                chatId: params.chatId,
                userId: params.userId,
                result: response.data
            }, 'Message sent to MAX');

            return response.data;
        } catch (error) {
            this.logError('sendMessage', error);
            return null;
        }
    }

    /**
     * Get file link (if needed in future)
     */
    async getFileLink(fileId: string): Promise<string | null> {
        // TBD: Implement based on MAX API for file retrieval
        return null;
    }

    private logError(method: string, error: unknown) {
        if (error instanceof AxiosError) {
            logger.error({
                method,
                status: error.response?.status,
                data: error.response?.data,
                message: error.message
            }, 'MAX Provider API error');
        } else {
            logger.error({ method, err: error }, 'MAX Provider internal error');
        }
    }
}

// Singleton instance
export const maxProvider = new MaxProviderService();
