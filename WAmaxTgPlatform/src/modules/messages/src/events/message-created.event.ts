import { BaseEvent } from './base.event';
import { Direction, MessageKind } from '../types/enums';

export interface MessageCreated extends BaseEvent {
  messageId: string;
  conversationId: string;
  direction: Direction;
  kind: MessageKind;
  senderId: string;
  channel: string;
  accountId: string;
}