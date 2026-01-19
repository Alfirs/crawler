import { DeliveryStatus } from '../types/enums';

export class MessageDeliveryState {
  messageId: string;
  status: DeliveryStatus;
  isFinal: boolean;
  reason?: {
    code: string;
    message?: string;
  };
  updatedAt: string;
}