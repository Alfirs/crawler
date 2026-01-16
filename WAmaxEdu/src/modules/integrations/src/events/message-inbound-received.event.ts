import { BaseEvent } from './base.event';
import { Channel, ParticipantType, MessageKind } from '../types/enums';
import { ConversationRef, ParticipantRef, MessageContent } from './types';

export interface MessageInboundReceived extends BaseEvent {
  channel: Channel;
  accountId: string;
  conversationRef: ConversationRef;
  externalMessageRef: {
    id: string;
    scope?: string;
  };
  sender: {
    participantRef: {
      type: ParticipantType;
      id: string;
    };
    displayName?: string;
  };
  message: {
    kind: MessageKind;
    content: MessageContent;
    context?: {
      replyToExternalMessageRef?: {
        id: string;
      };
      quotedText?: string;
    };
  };
  rawProviderRef?: {
    provider: string;
    payloadHash?: string;
  };
}