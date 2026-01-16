import { v4 as uuidv4 } from 'uuid';
import { ChannelConnectRequest, ChannelDisconnectRequest } from '../dto/channel.dto';
import { ChannelConnectionStateChanged } from '../events/channel-connection-state-changed.event';
import { EventPublisherService } from './event-publisher.service';
import { WhatsAppProviderService } from './providers/whatsapp-provider.service';
import { logger } from '@/config/logger.config';

interface ConnectResult {
  connectRequestId: string;
  state: string;
}

interface HealthResult {
  connectionState: string;
  lastSeenAt: string;
  details: Record<string, any>;
}

export class ChannelService {
  constructor(
    private readonly eventPublisher: EventPublisherService = new EventPublisherService(),
    private readonly whatsappProvider: WhatsAppProviderService = new WhatsAppProviderService()
  ) {}

  async connect(request: ChannelConnectRequest): Promise<ConnectResult> {
    const connectRequestId = uuidv4();

    try {
      logger.info(`Starting WhatsApp connection for account ${request.accountId}`);

      // Publish initial state
      await this.eventPublisher.publishChannelConnectionStateChanged({
        eventId: uuidv4(),
        occurredAt: new Date().toISOString(),
        channel: request.channel,
        accountId: request.accountId,
        connectRequestId,
        state: 'PENDING'
      });

      // Start async connection process
      this.performConnection(request, connectRequestId);

      return {
        connectRequestId,
        state: 'PENDING'
      };

    } catch (error) {
      logger.error({ err: error }, 'ChannelService.connect error');

      await this.eventPublisher.publishChannelConnectionStateChanged({
        eventId: uuidv4(),
        occurredAt: new Date().toISOString(),
        channel: request.channel,
        accountId: request.accountId,
        connectRequestId,
        state: 'FAILED',
        details: { error: error.message }
      });

      throw error;
    }
  }

  async disconnect(request: ChannelDisconnectRequest): Promise<void> {
    try {
      logger.info(`Starting WhatsApp disconnection for account ${request.accountId}`);

      // Perform async disconnect
      this.performDisconnection(request);

    } catch (error) {
      logger.error({ err: error }, 'ChannelService.disconnect error');
      throw error;
    }
  }

  async getHealth(channel: string, accountId: string): Promise<HealthResult> {
    if (channel !== 'WHATSAPP') {
      throw new Error('UNSUPPORTED_CHANNEL');
    }

    try {
      return await this.whatsappProvider.getHealth(accountId);
    } catch (error) {
      logger.error({ err: error }, 'ChannelService.getHealth error');
      throw new Error('CHANNEL_ACCOUNT_NOT_FOUND');
    }
  }

  private async performConnection(request: ChannelConnectRequest, connectRequestId: string): Promise<void> {
    try {
      // Update to awaiting user action (QR code, etc.)
      await this.eventPublisher.publishChannelConnectionStateChanged({
        eventId: uuidv4(),
        occurredAt: new Date().toISOString(),
        channel: request.channel,
        accountId: request.accountId,
        connectRequestId,
        state: 'AWAITING_USER_ACTION'
      });

      // Perform actual connection
      const result = await this.whatsappProvider.connect(request.accountId);

      // Update to connected
      await this.eventPublisher.publishChannelConnectionStateChanged({
        eventId: uuidv4(),
        occurredAt: new Date().toISOString(),
        channel: request.channel,
        accountId: request.accountId,
        connectRequestId,
        state: 'CONNECTED',
        details: { sessionId: result.sessionId }
      });

    } catch (error) {
      logger.error({ err: error }, 'ChannelService.performConnection error');

      await this.eventPublisher.publishChannelConnectionStateChanged({
        eventId: uuidv4(),
        occurredAt: new Date().toISOString(),
        channel: request.channel,
        accountId: request.accountId,
        connectRequestId,
        state: 'FAILED',
        details: { error: error.message }
      });
    }
  }

  private async performDisconnection(request: ChannelDisconnectRequest): Promise<void> {
    try {
      await this.whatsappProvider.disconnect(request.accountId);

      logger.info(`WhatsApp disconnected for account ${request.accountId}`);

    } catch (error) {
      logger.error({ err: error }, 'ChannelService.performDisconnection error');
      // Don't throw - disconnect should be best effort
    }
  }
}
