import { v4 as uuidv4 } from 'uuid';
import { MessageInboundReceived } from '@integrations/events/message-inbound-received.event';
import { MessageDeliveryStatusUpdated } from '@integrations/events/message-delivery-status-updated.event';
import { Message } from '../dto/message.dto';
import { Conversation } from '../dto/conversation.dto';
import { MessageDeliveryState } from '../dto/delivery-status.dto';
import { Direction } from '../types/enums';
import { DeduplicationService } from './dedup.service';
import { MessageEventPublisher } from './message-event-publisher.service';
import { messageStore } from './message-store.service';
import { logger } from '@/config/logger.config';

export class MessageProcessingService {
  constructor(
    private readonly dedupService: DeduplicationService = new DeduplicationService(),
    private readonly eventPublisher: MessageEventPublisher = new MessageEventPublisher()
  ) {}

  async processInboundMessage(event: MessageInboundReceived): Promise<void> {
    const dedupKey = this.dedupService.generateMessageDedupKey(
      event.channel,
      event.accountId,
      event.externalMessageRef.id
    );

    // Check if already processed
    const alreadyProcessed = await this.dedupService.isProcessed(dedupKey);
    if (alreadyProcessed) {
      logger.info(`Duplicate inbound message ignored: ${event.eventId}`);
      return;
    }

    try {
      // Upsert conversation
      const conversation = await this.upsertConversation(event);

      // Create message
      const message = await this.createMessage(event, conversation.conversationId);

      // Mark as processed
      await this.dedupService.markProcessed(event.eventId, dedupKey, message.messageId);

      // Publish internal event
      await this.eventPublisher.publishMessageCreated({
        eventId: uuidv4(),
        occurredAt: new Date().toISOString(),
        messageId: message.messageId,
        conversationId: conversation.conversationId,
        direction: Direction.INBOUND,
        kind: event.message.kind,
        senderId: event.sender.participantRef.id,
        channel: event.channel,
        accountId: event.accountId
      });

    } catch (error) {
      logger.error({ err: error }, 'MessageProcessingService.processInboundMessage error');
      throw error;
    }
  }

  async processDeliveryStatusUpdate(event: MessageDeliveryStatusUpdated): Promise<void> {
    const dedupKey = this.dedupService.generateStatusDedupKey(
      event.channel,
      event.accountId,
      event.externalMessageRef.id,
      event.status,
      event.occurredAt
    );

    // Check if already processed
    const alreadyProcessed = await this.dedupService.isProcessed(dedupKey);
    if (alreadyProcessed) {
      logger.info(`Duplicate status update ignored: ${event.eventId}`);
      return;
    }

    try {
      // Find message
      let message = await this.findMessage(event);

      if (!message) {
        // Orphan status update - log and skip or store for later
        logger.warn(`Orphan status update: ${event.eventId} - message not found`);
        await this.dedupService.markProcessed(event.eventId, dedupKey);
        return;
      }

      // Update delivery status
      await this.updateDeliveryStatus(message.messageId, event);

      // Mark as processed
      await this.dedupService.markProcessed(event.eventId, dedupKey, message.messageId);

      // Publish internal event
      await this.eventPublisher.publishStatusUpdated({
        eventId: uuidv4(),
        occurredAt: new Date().toISOString(),
        messageId: message.messageId,
        conversationId: message.conversationId,
        newStatus: event.status,
        isFinal: event.isFinal,
        channel: event.channel,
        accountId: event.accountId
      });

    } catch (error) {
      logger.error({ err: error }, 'MessageProcessingService.processDeliveryStatusUpdate error');
      throw error;
    }
  }

  private async upsertConversation(event: MessageInboundReceived): Promise<Conversation> {
    return messageStore.upsertConversation(
      event.accountId,
      event.channel,
      event.conversationRef
    );
  }

  private async createMessage(event: MessageInboundReceived, conversationId: string): Promise<Message> {
    const message: Message = {
      messageId: uuidv4(),
      conversationId,
      direction: Direction.INBOUND,
      externalMessageRef: event.externalMessageRef,
      kind: event.message.kind,
      content: event.message.content,
      sender: event.sender,
      occurredAt: event.occurredAt,
      createdAt: new Date().toISOString()
    };

    return messageStore.createMessage(message);
  }

  private async findMessage(event: MessageDeliveryStatusUpdated): Promise<Message | null> {
    // Try to find by clientMessageId first
    if (event.clientMessageId) {
      return messageStore.findMessageByClientMessageId(event.clientMessageId);
    }

    // Try to find by externalMessageRef
    if (event.externalMessageRef?.id) {
      return messageStore.findMessageByExternalRefId(event.externalMessageRef.id);
    }

    return null;
  }

  private async updateDeliveryStatus(messageId: string, event: MessageDeliveryStatusUpdated): Promise<void> {
    const deliveryState: MessageDeliveryState = {
      messageId,
      status: event.status,
      isFinal: event.isFinal,
      reason: event.reason,
      updatedAt: new Date().toISOString()
    };

    await messageStore.updateDeliveryStatus(deliveryState);
  }
}
