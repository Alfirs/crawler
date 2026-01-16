import { v4 as uuidv4 } from 'uuid';
import { OutboundMessageSendRequest } from '../dto/outbound-message-send.dto';
import { DeliveryStatus } from '../types/enums';
import { IntegrationsConfig } from '../config/integrations.config';
import { IdempotencyRecord, IdempotencyService } from './idempotency.service';
import { EventPublisherService } from './event-publisher.service';
import { WhatsAppProviderService } from './providers/whatsapp-provider.service';
import { logger } from '@/config/logger.config';

interface SendMessageResult {
  deliveryRequestId: string;
  status: DeliveryStatus;
}

export class OutboundMessageService {
  constructor(
    private readonly idempotencyService: IdempotencyService = new IdempotencyService(),
    private readonly eventPublisher: EventPublisherService = new EventPublisherService(),
    private readonly whatsappProvider: WhatsAppProviderService = new WhatsAppProviderService()
  ) {}

  async sendMessage(request: OutboundMessageSendRequest, idempotencyKey: string): Promise<SendMessageResult> {
    const cacheKey = idempotencyKey;
    const payloadHash = this.idempotencyService.computePayloadHash(request);

    // Check idempotency
    const existingRecord = await this.idempotencyService.get<SendMessageResult>(cacheKey);
    if (existingRecord) {
      if (existingRecord.payloadHash !== payloadHash) {
        const conflict: any = new Error('IDEMPOTENCY_CONFLICT');
        conflict.code = 'IDEMPOTENCY_CONFLICT';
        throw conflict;
      }

      logger.info(`Idempotent request detected for key: ${cacheKey}`);
      return existingRecord.response;
    }

    // Validate channel support
    if (!IntegrationsConfig.supportedChannels.includes(request.channel)) {
      throw new Error('UNSUPPORTED_CHANNEL');
    }

    // Validate account exists and is connected
    const accountConnected = await this.validateAccountConnection(request.accountId);
    if (!accountConnected) {
      throw new Error('CHANNEL_ACCOUNT_NOT_FOUND');
    }

    // Generate delivery request ID
    const deliveryRequestId = uuidv4();

    try {
      // Send message via provider
      const providerResult = await this.whatsappProvider.sendMessage(request);

      // Store result with TTL
      const result: SendMessageResult = {
        deliveryRequestId,
        status: DeliveryStatus.SENT
      };

      const record: IdempotencyRecord<SendMessageResult> = {
        payloadHash,
        response: result
      };

      await this.idempotencyService.set(cacheKey, record, IntegrationsConfig.idempotencyTTL);

      // Publish status update event
      await this.eventPublisher.publishMessageDeliveryStatusUpdated({
        eventId: uuidv4(),
        occurredAt: new Date().toISOString(),
        channel: request.channel,
        accountId: request.accountId,
        deliveryRequestId,
        clientMessageId: request.message.clientMessageId,
        externalMessageRef: { id: providerResult.messageId },
        status: DeliveryStatus.SENT,
        isFinal: false
      });

      return result;

    } catch (error: any) {
      logger.error({ err: error }, 'OutboundMessageService.sendMessage error');

      // Store failed result
      const result: SendMessageResult = {
        deliveryRequestId,
        status: DeliveryStatus.FAILED
      };

      const record: IdempotencyRecord<SendMessageResult> = {
        payloadHash,
        response: result
      };

      await this.idempotencyService.set(cacheKey, record, IntegrationsConfig.idempotencyTTL);

      // Publish failed status
      await this.eventPublisher.publishMessageDeliveryStatusUpdated({
        eventId: uuidv4(),
        occurredAt: new Date().toISOString(),
        channel: request.channel,
        accountId: request.accountId,
        deliveryRequestId,
        clientMessageId: request.message.clientMessageId,
        externalMessageRef: { id: 'unknown' },
        status: DeliveryStatus.FAILED,
        reason: {
          code: error.code || 'PROVIDER_ERROR',
          message: error.message
        },
        isFinal: true
      });

      throw error;
    }
  }

  private async validateAccountConnection(accountId: string): Promise<boolean> {
    // TODO: Check database for account connection status
    // For now, return true
    return true;
  }
}
