import { Channel, ConversationType } from '../types/enums';

export class ConversationRef {
  type: ConversationType;
  id: string;
}

export class Conversation {
  conversationId: string;
  channel: Channel;
  accountId: string;
  conversationRef: ConversationRef;
  createdAt: string;
  updatedAt: string;
}