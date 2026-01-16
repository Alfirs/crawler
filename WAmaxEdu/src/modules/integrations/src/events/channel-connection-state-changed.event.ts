import { BaseEvent } from './base.event';
import { Channel } from '../types/enums';

export interface ChannelConnectionStateChanged extends BaseEvent {
  channel: Channel;
  accountId: string;
  connectRequestId: string;
  state: 'PENDING' | 'AWAITING_USER_ACTION' | 'CONNECTED' | 'DISCONNECTED' | 'FAILED';
  details?: Record<string, any>;
}