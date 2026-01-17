import { v4 as uuidv4 } from 'uuid';
import { MessageInboundReceived } from '../events/message-inbound-received.event';
import { MessageDeliveryStatusUpdated } from '../events/message-delivery-status-updated.event';
import { Channel, ParticipantType, MessageKind, DeliveryStatus, ConversationType } from '../types/enums';
import { EventPublisherService } from './event-publisher.service';
import { logger } from '@/config/logger.config';
import { config } from '@/config/env.config';

import { bitrix24Provider } from './providers/bitrix24-provider.service';

export class InboundWebhookService {
  constructor(private readonly eventPublisher: EventPublisherService = new EventPublisherService()) { }

  async processWebhook(providerPayload: any): Promise<void> {
    try {
      // Auth TBD: shared secret signature header OR internal allowlist
      // For now, accept all requests (should be secured by network/firewall)

      logger.info('Processing inbound webhook');

      const { data, instanceName } = this.unwrapPayload(providerPayload);
      const payloads = Array.isArray(data) ? data : [data];

      for (const payload of payloads) {
        if (!payload || typeof payload !== 'object') {
          continue;
        }

        const event: MessageInboundReceived = {
          eventId: uuidv4(),
          occurredAt: new Date().toISOString(),
          channel: Channel.WHATSAPP,
          accountId: this.extractAccountId(payload, instanceName),
          conversationRef: {
            type: this.mapConversationType(payload),
            id: this.normalizeParticipant(payload.key?.remoteJid)
          },
          externalMessageRef: {
            id: payload.key?.id || 'unknown'
          },
          sender: {
            participantRef: {
              type: ParticipantType.USER,
              id: payload.key?.fromMe ? 'self' : this.normalizeParticipant(payload.key?.participant || payload.key?.remoteJid)
            },
            displayName: payload.pushName
          },
          message: {
            kind: this.mapMessageKind(payload),
            content: this.extractMessageContent(payload),
            context: this.extractMessageContext(payload)
          },
          rawProviderRef: {
            provider: 'evolution-api',
            payloadHash: this.hashPayload(payload)
          }
        };

        await this.eventPublisher.publishMessageInboundReceived(event);

        // Forward to Bitrix24 if configured
        if (bitrix24Provider.isConfigured()) {
          const content = event.message.content;
          const remoteJid = payload.key?.remoteJid || '';
          const phoneNumber = remoteJid.replace(/\D/g, ''); // Extract numbers only

          // Determine line ID from config or default to '1'
          const lineId = config.BITRIX24_TEST_LINE_ID || '1';

          // Prepare files if any
          let files: Array<{ name: string; link: string; type: string }> = [];
          if (content.mediaType && content.source?.url) {
            files.push({
              name: content.filename || content.caption || 'file',
              link: content.source.url,
              type: content.mimetype || 'application/octet-stream'
            });
          }

          if (remoteJid && content) {
            const messageText = content.text || content.caption || (content.mediaType ? `[${content.mediaType}]` : '');

            await bitrix24Provider.forwardExternalMessage({
              externalChatId: remoteJid,
              userName: event.sender.displayName || 'WhatsApp User',
              message: messageText,
              source: 'whatsapp'
            });
          }
        }

      }
    } catch (error) {
      logger.error({ err: error }, 'InboundWebhookService.processWebhook error');
      throw new Error('INVALID_PROVIDER_PAYLOAD');
    }
  }

  async processStatus(providerPayload: any): Promise<void> {
    try {
      logger.info('Processing inbound status update');

      const { data, instanceName } = this.unwrapPayload(providerPayload);
      const payloads = Array.isArray(data) ? data : [data];

      for (const payload of payloads) {
        if (!payload || typeof payload !== 'object') {
          continue;
        }

        const status = this.mapProviderStatus(payload.status);
        const event: MessageDeliveryStatusUpdated = {
          eventId: uuidv4(),
          occurredAt: new Date().toISOString(),
          channel: Channel.WHATSAPP,
          accountId: this.extractAccountId(payload, instanceName),
          externalMessageRef: {
            id: payload.key?.id || 'unknown'
          },
          status,
          reason: payload.error ? {
            code: payload.error.code,
            message: payload.error.message
          } : undefined,
          isFinal: status === DeliveryStatus.READ || status === DeliveryStatus.FAILED
        };

        await this.eventPublisher.publishMessageDeliveryStatusUpdated(event);

        // Update status in Bitrix24 if configured
        if (bitrix24Provider.isConfigured() && event.status) {
          const remoteJid = payload.key?.remoteJid;
          const messageId = payload.key?.id;

          if (remoteJid && messageId && (event.status === DeliveryStatus.DELIVERED || event.status === DeliveryStatus.READ)) {
            await bitrix24Provider.updateMessageStatus({
              lineId: '1', // Default line
              externalChatId: remoteJid,
              messageIds: [messageId],
              status: event.status === DeliveryStatus.READ ? 'read' : 'delivered'
            });
          }
        }
      }

    } catch (error) {
      logger.error({ err: error }, 'InboundWebhookService.processStatus error');
      throw new Error('INVALID_PROVIDER_PAYLOAD');
    }
  }

  isStatusEvent(eventName?: string): boolean {
    if (!eventName) {
      return false;
    }
    return eventName === 'send.message.update' || eventName === 'messages.update';
  }

  private unwrapPayload(payload: any): { event?: string; data: any; instanceName?: string } {
    if (payload && typeof payload === 'object' && 'data' in payload && 'event' in payload) {
      return {
        event: payload.event,
        data: payload.data,
        instanceName: payload.instanceName || payload.instanceId
      };
    }
    return { data: payload, instanceName: payload?.instanceName || payload?.instanceId };
  }

  private extractAccountId(payload: any, instanceName?: string): string {
    return instanceName || payload.instanceName || payload.instanceId || 'default';
  }

  private normalizeParticipant(remoteId?: string): string {
    if (!remoteId) {
      return 'unknown';
    }
    const [normalized] = remoteId.split('@');
    return normalized || remoteId;
  }

  private mapConversationType(payload: any): ConversationType {
    // Determine conversation type from provider payload
    const remoteJid = payload.key?.remoteJid;
    if (remoteJid?.includes('@g.us')) {
      return ConversationType.THREAD; // Group chat
    }
    return ConversationType.EXTERNAL_PARTICIPANT; // Direct message
  }

  private mapMessageKind(payload: any): MessageKind {
    // Map Evolution API message types to internal kinds
    const message = payload.message;
    if (message?.conversation || message?.extendedTextMessage) return MessageKind.TEXT;
    if (message?.imageMessage || message?.documentMessage || message?.videoMessage || message?.audioMessage) return MessageKind.MEDIA;
    if (message?.locationMessage) return MessageKind.LOCATION;
    if (message?.contactMessage) return MessageKind.CONTACT;
    if (message?.reactionMessage) return MessageKind.REACTION;
    if (message?.buttonsMessage || message?.listMessage) return MessageKind.INTERACTIVE;
    return MessageKind.TEXT; // Default
  }

  private extractMessageContent(payload: any): any {
    // Extract message content based on type
    const message = payload.message;
    if (message?.conversation) {
      return { text: message.conversation, format: 'PLAIN' };
    }
    if (message?.extendedTextMessage?.text) {
      return { text: message.extendedTextMessage.text, format: 'PLAIN' };
    }
    if (message?.imageMessage) {
      return {
        mediaType: 'IMAGE',
        source: { url: message.imageMessage.url || message.imageMessage.mediaUrl },
        caption: message.imageMessage.caption,
        mimetype: message.imageMessage.mimetype
      };
    }
    if (message?.videoMessage) {
      return {
        mediaType: 'VIDEO',
        source: { url: message.videoMessage.url || message.videoMessage.mediaUrl },
        caption: message.videoMessage.caption,
        mimetype: message.videoMessage.mimetype
      };
    }
    if (message?.documentMessage) {
      return {
        mediaType: 'FILE',
        source: { url: message.documentMessage.url || message.documentMessage.mediaUrl },
        caption: message.documentMessage.caption,
        filename: message.documentMessage.fileName || message.documentMessage.name,
        mimetype: message.documentMessage.mimetype
      };
    }
    if (message?.audioMessage) {
      return {
        mediaType: 'AUDIO',
        source: { url: message.audioMessage.url || message.audioMessage.mediaUrl },
        mimetype: message.audioMessage.mimetype
      };
    }
    if (message?.locationMessage) {
      return {
        latitude: message.locationMessage.degreesLatitude,
        longitude: message.locationMessage.degreesLongitude,
        address: message.locationMessage.address,
        title: message.locationMessage.name
      };
    }
    if (message?.contactMessage) {
      return {
        contacts: [
          {
            displayName: message.contactMessage.displayName || payload.pushName || 'Contact',
            phones: message.contactMessage.phoneNumber ? [{ number: message.contactMessage.phoneNumber }] : []
          }
        ]
      };
    }
    if (message?.reactionMessage) {
      return {
        targetMessageId: message.reactionMessage?.key?.id,
        reaction: message.reactionMessage?.text || ''
      };
    }
    if (message?.buttonsMessage) {
      return {
        interactiveType: 'BUTTONS',
        bodyText: message.buttonsMessage.contentText || '',
        footerText: message.buttonsMessage.footerText,
        actions: {
          buttons: (message.buttonsMessage.buttons || []).map((button: any) => ({
            actionId: button.buttonId || button.buttonID || '',
            title: button.buttonText?.displayText || '',
            kind: 'REPLY'
          }))
        }
      };
    }
    if (message?.listMessage) {
      return {
        interactiveType: 'LIST',
        bodyText: message.listMessage.description || message.listMessage.title || '',
        footerText: message.listMessage.footerText,
        actions: {
          buttonTitle: message.listMessage.buttonText || 'Open',
          sections: (message.listMessage.sections || []).map((section: any) => ({
            title: section.title,
            items: (section.rows || []).map((row: any) => ({
              actionId: row.rowId,
              title: row.title,
              description: row.description
            }))
          }))
        }
      };
    }
    return { text: 'Unsupported message type', format: 'PLAIN' };
  }

  private extractMessageContext(payload: any): any {
    // Extract message context (replies, quotes)
    const contextInfo = payload.contextInfo || payload.message?.contextInfo;
    if (contextInfo) {
      return {
        replyToExternalMessageRef: contextInfo.quotedMessage ? { id: contextInfo.stanzaId } : undefined,
        quotedText: contextInfo.quotedMessage?.conversation || contextInfo.quotedMessage?.extendedTextMessage?.text
      };
    }
    return undefined;
  }

  private mapProviderStatus(providerStatus: string): DeliveryStatus {
    // Map Evolution API statuses to internal statuses
    if (typeof providerStatus === 'number') {
      switch (providerStatus) {
        case 1: return DeliveryStatus.SENT;
        case 2: return DeliveryStatus.DELIVERED;
        case 3: return DeliveryStatus.READ;
        case 4: return DeliveryStatus.READ;
        default: return DeliveryStatus.PENDING;
      }
    }

    switch (providerStatus) {
      case 'SERVER_ACK':
      case 'SENT':
        return DeliveryStatus.SENT;
      case 'DELIVERY_ACK':
      case 'DELIVERED':
        return DeliveryStatus.DELIVERED;
      case 'READ':
      case 'PLAYED':
        return DeliveryStatus.READ;
      case 'ERROR':
      case 'FAILED':
        return DeliveryStatus.FAILED;
      default:
        return DeliveryStatus.PENDING;
    }
  }

  private hashPayload(payload: any): string {
    // Simple hash for payload deduplication
    return require('crypto').createHash('md5').update(JSON.stringify(payload)).digest('hex');
  }
}
