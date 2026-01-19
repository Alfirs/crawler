import { Channel, ConversationType, MessageKind } from '../types/enums';
import { TextContent, MediaContent, LocationContent, ContactContent, InteractiveContent, ReactionContent } from './content.dto';

export class ConversationRef {
  type: ConversationType;
  id: string;
}

export class Context {
  replyToMessageId?: string;
  forwarded?: boolean;
  metadata?: Record<string, any>;
}

export class OutboundMessageSendRequest {
  channel: Channel;
  accountId: string;
  conversationRef: ConversationRef;
  context?: Context;
  requestedAt?: string;
  message: {
    clientMessageId: string;
    kind: MessageKind;
    content: TextContent | MediaContent | LocationContent | ContactContent | InteractiveContent | ReactionContent;
  };
}
