import { v4 as uuidv4 } from 'uuid';
import { config } from '@/config/env.config';
import { database } from '@/config/database.config';
import { logger } from '@/config/logger.config';
import { Conversation, ConversationRef } from '../dto/conversation.dto';
import { Message } from '../dto/message.dto';
import { MessageDeliveryState } from '../dto/delivery-status.dto';

interface GetMessagesOptions {
  limit: number;
  offset: number;
  direction?: 'INBOUND' | 'OUTBOUND';
}

interface MessageStoreDriver {
  upsertConversation(accountId: string, channel: string, conversationRef: ConversationRef): Promise<Conversation>;
  createMessage(message: Message): Promise<Message>;
  updateDeliveryStatus(state: MessageDeliveryState): Promise<void>;
  findMessageByClientMessageId(clientMessageId: string): Promise<Message | null>;
  findMessageByExternalRefId(externalMessageRefId: string): Promise<Message | null>;
  getConversations(accountId: string, channel: string, limit: number, offset: number): Promise<Conversation[]>;
  getMessages(conversationId: string, options: GetMessagesOptions): Promise<Message[]>;
  getMessage(messageId: string): Promise<Message | null>;
  isProcessed(dedupKey: string): Promise<boolean>;
  markProcessed(eventId: string, dedupKey: string, resultRef?: string): Promise<void>;
}

class InMemoryMessageStore implements MessageStoreDriver {
  private conversations = new Map<string, Conversation>();
  private conversationByRef = new Map<string, string>();
  private messages = new Map<string, Message>();
  private messagesByConversation = new Map<string, string[]>();
  private messageByClientMessageId = new Map<string, string>();
  private messageByExternalRefId = new Map<string, string>();
  private deliveryStates = new Map<string, MessageDeliveryState>();
  private processedEvents = new Map<string, { eventId: string; processedAt: string; resultRef?: string }>();

  async upsertConversation(accountId: string, channel: string, conversationRef: ConversationRef): Promise<Conversation> {
    const key = `${channel}:${accountId}:${conversationRef.type}:${conversationRef.id}`;
    const existingId = this.conversationByRef.get(key);
    const now = new Date().toISOString();

    if (existingId) {
      const existing = this.conversations.get(existingId);
      if (existing) {
        existing.updatedAt = now;
        this.conversations.set(existingId, existing);
        return existing;
      }
    }

    const conversation: Conversation = {
      conversationId: uuidv4(),
      channel: channel as Conversation['channel'],
      accountId,
      conversationRef,
      createdAt: now,
      updatedAt: now,
    };

    this.conversations.set(conversation.conversationId, conversation);
    this.conversationByRef.set(key, conversation.conversationId);
    return conversation;
  }

  async createMessage(message: Message): Promise<Message> {
    this.messages.set(message.messageId, message);
    const list = this.messagesByConversation.get(message.conversationId) || [];
    list.push(message.messageId);
    this.messagesByConversation.set(message.conversationId, list);

    if (message.clientMessageId) {
      this.messageByClientMessageId.set(message.clientMessageId, message.messageId);
    }
    if (message.externalMessageRef?.id) {
      this.messageByExternalRefId.set(message.externalMessageRef.id, message.messageId);
    }

    const conversation = this.conversations.get(message.conversationId);
    if (conversation) {
      conversation.updatedAt = new Date().toISOString();
      this.conversations.set(conversation.conversationId, conversation);
    }

    return message;
  }

  async updateDeliveryStatus(state: MessageDeliveryState): Promise<void> {
    this.deliveryStates.set(state.messageId, state);
  }

  async findMessageByClientMessageId(clientMessageId: string): Promise<Message | null> {
    const messageId = this.messageByClientMessageId.get(clientMessageId);
    if (!messageId) {
      return null;
    }
    return this.messages.get(messageId) || null;
  }

  async findMessageByExternalRefId(externalMessageRefId: string): Promise<Message | null> {
    const messageId = this.messageByExternalRefId.get(externalMessageRefId);
    if (!messageId) {
      return null;
    }
    return this.messages.get(messageId) || null;
  }

  async getConversations(accountId: string, channel: string, limit: number, offset: number): Promise<Conversation[]> {
    const conversations = Array.from(this.conversations.values())
      .filter((conv) => conv.accountId === accountId && conv.channel === channel)
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));

    return conversations.slice(offset, offset + limit);
  }

  async getMessages(conversationId: string, options: GetMessagesOptions): Promise<Message[]> {
    const messageIds = this.messagesByConversation.get(conversationId) || [];
    const messages = messageIds
      .map((id) => this.messages.get(id))
      .filter((msg): msg is Message => Boolean(msg));

    const filtered = options.direction
      ? messages.filter((msg) => msg.direction === options.direction)
      : messages;

    const sorted = filtered.sort((a, b) => a.occurredAt.localeCompare(b.occurredAt));
    return sorted.slice(options.offset, options.offset + options.limit);
  }

  async getMessage(messageId: string): Promise<Message | null> {
    return this.messages.get(messageId) || null;
  }

  async isProcessed(dedupKey: string): Promise<boolean> {
    return this.processedEvents.has(dedupKey);
  }

  async markProcessed(eventId: string, dedupKey: string, resultRef?: string): Promise<void> {
    this.processedEvents.set(dedupKey, {
      eventId,
      processedAt: new Date().toISOString(),
      resultRef,
    });
  }
}

class PrismaMessageStore implements MessageStoreDriver {
  private get client(): any {
    return database.client as any;
  }

  async upsertConversation(accountId: string, channel: string, conversationRef: ConversationRef): Promise<Conversation> {
    const now = new Date();
    const conversationId = uuidv4();
    const record = await this.client.conversation.upsert({
      where: {
        accountId_channel_conversationRefType_conversationRefId: {
          accountId,
          channel,
          conversationRefType: conversationRef.type,
          conversationRefId: conversationRef.id,
        },
      },
      update: {
        updatedAt: now,
      },
      create: {
        conversationId,
        accountId,
        channel,
        conversationRefType: conversationRef.type,
        conversationRefId: conversationRef.id,
        createdAt: now,
        updatedAt: now,
      },
    });

    return {
      conversationId: record.conversationId,
      channel: record.channel,
      accountId: record.accountId,
      conversationRef: {
        type: record.conversationRefType,
        id: record.conversationRefId,
      },
      createdAt: record.createdAt.toISOString(),
      updatedAt: record.updatedAt.toISOString(),
    };
  }

  async createMessage(message: Message): Promise<Message> {
    const record = await this.client.message.create({
      data: {
        messageId: message.messageId,
        conversationId: message.conversationId,
        direction: message.direction,
        clientMessageId: message.clientMessageId,
        externalMessageRefId: message.externalMessageRef?.id,
        kind: message.kind,
        content: message.content,
        sender: message.sender,
        occurredAt: new Date(message.occurredAt),
        createdAt: new Date(message.createdAt),
      },
    });

    return this.mapMessage(record);
  }

  async updateDeliveryStatus(state: MessageDeliveryState): Promise<void> {
    await this.client.messageDeliveryState.upsert({
      where: { messageId: state.messageId },
      update: {
        status: state.status,
        isFinal: state.isFinal,
        reason: state.reason,
        updatedAt: new Date(state.updatedAt),
      },
      create: {
        messageId: state.messageId,
        status: state.status,
        isFinal: state.isFinal,
        reason: state.reason,
        updatedAt: new Date(state.updatedAt),
      },
    });
  }

  async findMessageByClientMessageId(clientMessageId: string): Promise<Message | null> {
    const record = await this.client.message.findFirst({
      where: { clientMessageId },
    });
    return record ? this.mapMessage(record) : null;
  }

  async findMessageByExternalRefId(externalMessageRefId: string): Promise<Message | null> {
    const record = await this.client.message.findFirst({
      where: { externalMessageRefId },
    });
    return record ? this.mapMessage(record) : null;
  }

  async getConversations(accountId: string, channel: string, limit: number, offset: number): Promise<Conversation[]> {
    const records = await this.client.conversation.findMany({
      where: { accountId, channel },
      orderBy: { updatedAt: 'desc' },
      take: limit,
      skip: offset,
    });

    return records.map((record: any) => ({
      conversationId: record.conversationId,
      channel: record.channel,
      accountId: record.accountId,
      conversationRef: {
        type: record.conversationRefType,
        id: record.conversationRefId,
      },
      createdAt: record.createdAt.toISOString(),
      updatedAt: record.updatedAt.toISOString(),
    }));
  }

  async getMessages(conversationId: string, options: GetMessagesOptions): Promise<Message[]> {
    const where: Record<string, any> = { conversationId };
    if (options.direction) {
      where.direction = options.direction;
    }

    const records = await this.client.message.findMany({
      where,
      orderBy: { occurredAt: 'asc' },
      take: options.limit,
      skip: options.offset,
    });

    return records.map((record: any) => this.mapMessage(record));
  }

  async getMessage(messageId: string): Promise<Message | null> {
    const record = await this.client.message.findUnique({
      where: { messageId },
    });
    return record ? this.mapMessage(record) : null;
  }

  async isProcessed(dedupKey: string): Promise<boolean> {
    const record = await this.client.processedEvent.findUnique({
      where: { dedupKey },
    });
    return Boolean(record);
  }

  async markProcessed(eventId: string, dedupKey: string, resultRef?: string): Promise<void> {
    await this.client.processedEvent.upsert({
      where: { dedupKey },
      update: {
        eventId,
        processedAt: new Date(),
        resultRef,
      },
      create: {
        dedupKey,
        eventId,
        processedAt: new Date(),
        resultRef,
      },
    });
  }

  private mapMessage(record: any): Message {
    return {
      messageId: record.messageId,
      conversationId: record.conversationId,
      direction: record.direction,
      clientMessageId: record.clientMessageId || undefined,
      externalMessageRef: record.externalMessageRefId
        ? { id: record.externalMessageRefId }
        : undefined,
      kind: record.kind,
      content: record.content,
      sender: record.sender,
      occurredAt: record.occurredAt.toISOString(),
      createdAt: record.createdAt.toISOString(),
    };
  }
}

class MessageStore {
  private readonly memoryStore = new InMemoryMessageStore();
  private readonly prismaStore = new PrismaMessageStore();
  private warnedFallback = false;

  private getStore(): MessageStoreDriver {
    if (config.MESSAGE_STORE === 'database') {
      if (!database.isConnected) {
        if (config.NODE_ENV === 'production') {
          throw new Error('MESSAGE_STORE_DATABASE_REQUIRED');
        }
        if (!this.warnedFallback) {
          logger.warn('Database not connected; falling back to memory message store');
          this.warnedFallback = true;
        }
        return this.memoryStore;
      }
      return this.prismaStore;
    }

    if (config.NODE_ENV === 'production') {
      throw new Error('MESSAGE_STORE_MEMORY_NOT_ALLOWED_IN_PROD');
    }

    return this.memoryStore;
  }

  async upsertConversation(accountId: string, channel: string, conversationRef: ConversationRef): Promise<Conversation> {
    return this.getStore().upsertConversation(accountId, channel, conversationRef);
  }

  async createMessage(message: Message): Promise<Message> {
    return this.getStore().createMessage(message);
  }

  async updateDeliveryStatus(state: MessageDeliveryState): Promise<void> {
    return this.getStore().updateDeliveryStatus(state);
  }

  async findMessageByClientMessageId(clientMessageId: string): Promise<Message | null> {
    return this.getStore().findMessageByClientMessageId(clientMessageId);
  }

  async findMessageByExternalRefId(externalMessageRefId: string): Promise<Message | null> {
    return this.getStore().findMessageByExternalRefId(externalMessageRefId);
  }

  async getConversations(accountId: string, channel: string, limit: number, offset: number): Promise<Conversation[]> {
    return this.getStore().getConversations(accountId, channel, limit, offset);
  }

  async getMessages(conversationId: string, options: GetMessagesOptions): Promise<Message[]> {
    return this.getStore().getMessages(conversationId, options);
  }

  async getMessage(messageId: string): Promise<Message | null> {
    return this.getStore().getMessage(messageId);
  }

  async isProcessed(dedupKey: string): Promise<boolean> {
    return this.getStore().isProcessed(dedupKey);
  }

  async markProcessed(eventId: string, dedupKey: string, resultRef?: string): Promise<void> {
    return this.getStore().markProcessed(eventId, dedupKey, resultRef);
  }
}

export const messageStore = new MessageStore();
