import { Direction, MessageKind, ParticipantType } from '../types/enums';

export class MessageSender {
  participantRef: {
    type: ParticipantType;
    id: string;
  };
  displayName?: string;
}

export type MessageContent = Record<string, any>;

export class Message {
  messageId: string;
  conversationId: string;
  direction: Direction;
  clientMessageId?: string; // For outbound messages
  externalMessageRef?: {
    id: string;
    scope?: string;
  };
  kind: MessageKind;
  content: MessageContent;
  sender: MessageSender;
  occurredAt: string;
  createdAt: string;
}
