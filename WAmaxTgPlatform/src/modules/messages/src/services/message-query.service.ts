import { Conversation } from '../dto/conversation.dto';
import { Message } from '../dto/message.dto';
import { messageStore } from './message-store.service';
import { logger } from '@/config/logger.config';

interface GetMessagesOptions {
  limit: number;
  offset: number;
  direction?: 'INBOUND' | 'OUTBOUND';
}

export class MessageQueryService {
  async getConversations(
    accountId: string,
    channel: string,
    limit: number,
    offset: number
  ): Promise<Conversation[]> {
    try {
      return await messageStore.getConversations(accountId, channel, limit, offset);
    } catch (error) {
      logger.error({ err: error }, 'MessageQueryService.getConversations error');
      throw error;
    }
  }

  async getMessages(
    conversationId: string,
    options: GetMessagesOptions
  ): Promise<Message[]> {
    try {
      return await messageStore.getMessages(conversationId, options);
    } catch (error) {
      logger.error({ err: error }, 'MessageQueryService.getMessages error');
      throw error;
    }
  }

  async getMessage(messageId: string): Promise<Message | null> {
    try {
      return await messageStore.getMessage(messageId);
    } catch (error) {
      logger.error({ err: error }, 'MessageQueryService.getMessage error');
      throw error;
    }
  }
}
