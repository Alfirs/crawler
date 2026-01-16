import { BaseEvent } from './base.event';
import { DeliveryStatus } from '../types/enums';

export interface MessageStatusUpdated extends BaseEvent {
  messageId: string;
  conversationId: string;
  oldStatus?: DeliveryStatus;
  newStatus: DeliveryStatus;
  isFinal: boolean;
  channel: string;
  accountId: string;
}