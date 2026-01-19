import { BaseEvent } from './base.event';
import { Channel, DeliveryStatus } from '../types/enums';

export interface MessageDeliveryStatusUpdated extends BaseEvent {
  channel: Channel;
  accountId: string;
  deliveryRequestId?: string;
  clientMessageId?: string;
  externalMessageRef: {
    id: string;
  };
  status: DeliveryStatus;
  reason?: {
    code: string;
    message?: string;
  };
  isFinal: boolean;
}