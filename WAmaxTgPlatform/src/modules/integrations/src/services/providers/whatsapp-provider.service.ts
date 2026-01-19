import axios, { AxiosInstance } from 'axios';
import { v4 as uuidv4 } from 'uuid';
import { OutboundMessageSendRequest } from '../../dto/outbound-message-send.dto';
import {
  MessageKind,
  MediaType,
  InteractiveType,
  ButtonKind,
  ConversationType,
  ConnectionState
} from '../../types/enums';
import { config } from '@/config/env.config';
import { logger } from '@/config/logger.config';

interface ProviderSendResult {
  messageId: string;
  status: string;
}

interface ProviderConnectResult {
  sessionId: string;
  qrCode?: string;
  details?: Record<string, any>;
}

export class WhatsAppProviderService {
  private client: AxiosInstance | null = null;

  async sendMessage(request: OutboundMessageSendRequest): Promise<ProviderSendResult> {
    if (this.shouldUseStub()) {
      return this.stubSendMessage(request);
    }

    this.ensureConfigured();

    const recipient = this.resolveRecipientId(request);
    const kind = request.message.kind;

    switch (kind) {
      case MessageKind.TEXT:
        return this.sendText(request.accountId, recipient, request.message.content);
      case MessageKind.MEDIA:
        return this.sendMedia(request.accountId, recipient, request.message.content);
      case MessageKind.LOCATION:
        return this.sendLocation(request.accountId, recipient, request.message.content);
      case MessageKind.CONTACT:
        return this.sendContact(request.accountId, recipient, request.message.content);
      case MessageKind.REACTION:
        return this.sendReaction(request.accountId, request.conversationRef, request.message.content);
      case MessageKind.INTERACTIVE:
        return this.sendInteractive(request.accountId, recipient, request.message.content);
      default:
        const unsupported: any = new Error('UNSUPPORTED_MESSAGE_TYPE');
        unsupported.code = 'UNSUPPORTED_MESSAGE_TYPE';
        throw unsupported;
    }
  }

  async connect(accountId: string): Promise<ProviderConnectResult> {
    if (this.shouldUseStub()) {
      logger.info(`Connecting WhatsApp account ${accountId} (stub)`);
      await new Promise(resolve => setTimeout(resolve, 200));
      return { sessionId: `session_${accountId}_${Date.now()}` };
    }

    this.ensureConfigured();

    await this.ensureInstance(accountId);
    await this.configureWebhook(accountId);

    const response = await this.getClient().get(`/instance/connect/${encodeURIComponent(accountId)}`);
    const payload = response?.data || {};
    const qrcode = this.extractQrCode(payload);

    return {
      sessionId: accountId,
      qrCode: qrcode,
      details: payload
    };
  }

  async disconnect(accountId: string): Promise<void> {
    if (this.shouldUseStub()) {
      logger.info(`Disconnecting WhatsApp account ${accountId} (stub)`);
      await new Promise(resolve => setTimeout(resolve, 100));
      return;
    }

    this.ensureConfigured();

    try {
      await this.getClient().delete(`/instance/logout/${encodeURIComponent(accountId)}`);
    } catch (error) {
      logger.error({ err: error }, 'WhatsApp disconnect failed');
      throw error;
    }
  }

  async getHealth(accountId: string): Promise<{ connectionState: string; lastSeenAt: string; details: any }> {
    if (this.shouldUseStub()) {
      return {
        connectionState: 'CONNECTED',
        lastSeenAt: new Date().toISOString(),
        details: {
          provider: 'whatsapp',
          mode: 'stub'
        }
      };
    }

    this.ensureConfigured();

    try {
      const response = await this.getClient().get(`/instance/connectionState/${encodeURIComponent(accountId)}`);
      const state = response?.data?.instance?.state || 'unknown';

      return {
        connectionState: this.mapConnectionState(state),
        lastSeenAt: new Date().toISOString(),
        details: response?.data
      };
    } catch (error) {
      logger.error({ err: error }, 'WhatsApp health check failed');
      throw error;
    }
  }

  private shouldUseStub(): boolean {
    if (config.NODE_ENV === 'test') {
      return true;
    }
    return !config.WHATSAPP_PROVIDER_BASE_URL || !config.WHATSAPP_PROVIDER_API_KEY;
  }

  private ensureConfigured(): void {
    if (!config.WHATSAPP_PROVIDER_BASE_URL || !config.WHATSAPP_PROVIDER_API_KEY) {
      if (config.NODE_ENV === 'production') {
        throw new Error('WHATSAPP_PROVIDER_NOT_CONFIGURED');
      }
    }
  }

  private getClient(): AxiosInstance {
    if (this.client) {
      return this.client;
    }

    const baseUrl = (config.WHATSAPP_PROVIDER_BASE_URL || '').replace(/\/+$/, '');
    this.client = axios.create({
      baseURL: baseUrl,
      timeout: config.WHATSAPP_PROVIDER_TIMEOUT_MS,
      headers: {
        apikey: config.WHATSAPP_PROVIDER_API_KEY || ''
      }
    });

    return this.client;
  }

  private async ensureInstance(accountId: string): Promise<void> {
    try {
      await this.getClient().post('/instance/create', {
        instanceName: accountId
      });
    } catch (error: any) {
      const status = error?.response?.status;
      if (status === 409 || status === 400) {
        logger.warn(`Instance ${accountId} may already exist`);
        return;
      }
      logger.error({ err: error }, 'Failed to create instance');
      throw error;
    }
  }

  private async configureWebhook(accountId: string): Promise<void> {
    if (!config.WHATSAPP_PROVIDER_WEBHOOK_URL) {
      return;
    }

    const events = this.parseWebhookEvents();
    const payload = {
      webhook: {
        enabled: true,
        url: config.WHATSAPP_PROVIDER_WEBHOOK_URL,
        events,
        byEvents: config.WHATSAPP_PROVIDER_WEBHOOK_BY_EVENTS,
      }
    };

    try {
      await this.getClient().post(`/webhook/set/${encodeURIComponent(accountId)}`, payload);
    } catch (error) {
      logger.error({ err: error }, 'Failed to configure provider webhook');
      throw error;
    }
  }

  private parseWebhookEvents(): string[] {
    const raw = config.WHATSAPP_PROVIDER_WEBHOOK_EVENTS;
    if (!raw) {
      return ['messages.upsert', 'send.message.update'];
    }
    return raw
      .split(',')
      .map((value) => value.trim())
      .filter((value) => value.length > 0);
  }

  private extractQrCode(payload: any): string | undefined {
    if (!payload) {
      return undefined;
    }
    return (
      payload?.qrcode?.base64 ||
      payload?.qrcode?.code ||
      payload?.qrcode?.pairingCode ||
      payload?.qrcode
    );
  }

  private resolveRecipientId(request: OutboundMessageSendRequest): string {
    const id = request.conversationRef?.id;
    if (!id) {
      const error: any = new Error('UNSUPPORTED_MESSAGE_TYPE');
      error.code = 'UNSUPPORTED_MESSAGE_TYPE';
      throw error;
    }

    if (request.conversationRef?.type === ConversationType.THREAD) {
      return id.includes('@g.us') ? id : `${id}@g.us`;
    }

    return id.replace(/@s\.whatsapp\.net$/i, '').replace(/@c\.us$/i, '');
  }

  private async sendText(accountId: string, number: string, content: any): Promise<ProviderSendResult> {
    const text = content?.text;
    if (!text) {
      const error: any = new Error('UNSUPPORTED_MESSAGE_TYPE');
      error.code = 'UNSUPPORTED_MESSAGE_TYPE';
      throw error;
    }

    const response = await this.getClient().post(`/message/sendText/${encodeURIComponent(accountId)}`, {
      number,
      text
    });

    return this.normalizeProviderResponse(response?.data);
  }

  private async sendMedia(accountId: string, number: string, content: any): Promise<ProviderSendResult> {
    const sourceUrl = content?.source?.url;
    if (!sourceUrl) {
      const error: any = new Error('UNSUPPORTED_MESSAGE_TYPE');
      error.code = 'UNSUPPORTED_MESSAGE_TYPE';
      throw error;
    }

    const mediaType = this.mapMediaType(content?.mediaType);
    const payload: Record<string, any> = {
      number,
      mediatype: mediaType,
      media: sourceUrl
    };

    if (content?.caption) {
      payload.caption = content.caption;
    }
    if (content?.filename) {
      payload.fileName = content.filename;
    }
    if (content?.mimeType) {
      payload.mimetype = content.mimeType;
    }

    const response = await this.getClient().post(`/message/sendMedia/${encodeURIComponent(accountId)}`, payload);
    return this.normalizeProviderResponse(response?.data);
  }

  private async sendLocation(accountId: string, number: string, content: any): Promise<ProviderSendResult> {
    if (content?.latitude === undefined || content?.longitude === undefined) {
      const error: any = new Error('UNSUPPORTED_MESSAGE_TYPE');
      error.code = 'UNSUPPORTED_MESSAGE_TYPE';
      throw error;
    }

    const payload = {
      number,
      latitude: content.latitude,
      longitude: content.longitude,
      name: content.title || '',
      address: content.address || ''
    };

    const response = await this.getClient().post(`/message/sendLocation/${encodeURIComponent(accountId)}`, payload);
    return this.normalizeProviderResponse(response?.data);
  }

  private async sendContact(accountId: string, number: string, content: any): Promise<ProviderSendResult> {
    const contacts = Array.isArray(content?.contacts) ? content.contacts : [];
    if (!contacts.length) {
      const error: any = new Error('UNSUPPORTED_MESSAGE_TYPE');
      error.code = 'UNSUPPORTED_MESSAGE_TYPE';
      throw error;
    }

    const payload = {
      number,
      contact: contacts.map((contact: any) => {
        const phone = contact?.phones?.[0]?.number;
        return {
          fullName: contact?.displayName || phone || 'Unknown',
          phoneNumber: phone || '',
          organization: contact?.organization?.company,
          email: contact?.emails?.[0]?.email,
          url: contact?.organization?.title
        };
      })
    };

    const response = await this.getClient().post(`/message/sendContact/${encodeURIComponent(accountId)}`, payload);
    return this.normalizeProviderResponse(response?.data);
  }

  private async sendReaction(accountId: string, conversationRef: any, content: any): Promise<ProviderSendResult> {
    if (!content?.targetMessageId) {
      const error: any = new Error('UNSUPPORTED_MESSAGE_TYPE');
      error.code = 'UNSUPPORTED_MESSAGE_TYPE';
      throw error;
    }

    const remoteJid = this.resolveReactionRemoteJid(conversationRef);
    const payload = {
      key: {
        id: content.targetMessageId,
        remoteJid,
        fromMe: true
      },
      reaction: content.reaction || ''
    };

    const response = await this.getClient().post(`/message/sendReaction/${encodeURIComponent(accountId)}`, payload);
    return this.normalizeProviderResponse(response?.data);
  }

  private async sendInteractive(accountId: string, number: string, content: any): Promise<ProviderSendResult> {
    if (content?.interactiveType === InteractiveType.LIST) {
      const payload = {
        number,
        title: content.bodyText || '',
        description: content.bodyText || '',
        footerText: content.footerText || '',
        buttonText: content.actions?.buttonTitle || 'Open',
        sections: this.mapListSections(content.actions?.sections)
      };

      const response = await this.getClient().post(`/message/sendList/${encodeURIComponent(accountId)}`, payload);
      return this.normalizeProviderResponse(response?.data);
    }

    const payload = {
      number,
      title: content.bodyText || '',
      description: content.bodyText || '',
      footer: content.footerText || '',
      buttons: this.mapButtons(content.actions?.buttons)
    };

    const response = await this.getClient().post(`/message/sendButtons/${encodeURIComponent(accountId)}`, payload);
    return this.normalizeProviderResponse(response?.data);
  }

  private mapButtons(buttons: any[]): any[] {
    if (!Array.isArray(buttons)) {
      return [];
    }
    return buttons.map((button) => {
      const mapped: Record<string, any> = {
        type: this.mapButtonType(button.kind),
        displayText: button.title,
        id: button.actionId
      };

      if (button.kind === ButtonKind.URL) {
        mapped.url = button.url;
      }
      if (button.kind === ButtonKind.CALL) {
        mapped.phoneNumber = button.phone;
      }

      return mapped;
    });
  }

  private mapListSections(sections: any[]): any[] {
    if (!Array.isArray(sections)) {
      return [];
    }
    return sections.map((section) => ({
      title: section.title || '',
      rows: Array.isArray(section.items)
        ? section.items.map((item: any) => ({
            rowId: item.actionId,
            title: item.title,
            description: item.description
          }))
        : []
    }));
  }

  private mapMediaType(mediaType?: MediaType): string {
    switch (mediaType) {
      case MediaType.IMAGE:
        return 'image';
      case MediaType.VIDEO:
        return 'video';
      case MediaType.AUDIO:
        return 'audio';
      case MediaType.FILE:
        return 'document';
      default:
        return 'document';
    }
  }

  private mapButtonType(kind?: ButtonKind): string {
    switch (kind) {
      case ButtonKind.URL:
        return 'url';
      case ButtonKind.CALL:
        return 'call';
      case ButtonKind.REPLY:
      default:
        return 'reply';
    }
  }

  private resolveReactionRemoteJid(conversationRef?: any): string {
    const id = conversationRef?.id || '';
    if (conversationRef?.type === ConversationType.THREAD) {
      return id.includes('@g.us') ? id : `${id}@g.us`;
    }
    return id.includes('@') ? id : `${id}@s.whatsapp.net`;
  }

  private normalizeProviderResponse(payload: any): ProviderSendResult {
    const messageId = this.extractMessageId(payload);
    return {
      messageId: messageId || `wa_${Date.now()}_${uuidv4()}`,
      status: 'sent'
    };
  }

  private extractMessageId(payload: any): string | undefined {
    return (
      payload?.key?.id ||
      payload?.messageId ||
      payload?.id ||
      payload?.response?.key?.id ||
      payload?.response?.messageId
    );
  }

  private mapConnectionState(state: string): string {
    switch (state) {
      case 'open':
        return ConnectionState.CONNECTED;
      case 'close':
        return ConnectionState.DISCONNECTED;
      case 'connecting':
        return ConnectionState.CONNECTING;
      case 'refused':
        return ConnectionState.FAILED;
      default:
        return ConnectionState.PENDING;
    }
  }

  private async stubSendMessage(request: OutboundMessageSendRequest): Promise<ProviderSendResult> {
    logger.info(`Sending WhatsApp message to account ${request.accountId} (stub)`);
    await new Promise(resolve => setTimeout(resolve, 100));
    return {
      messageId: `wa_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      status: 'sent'
    };
  }
}
