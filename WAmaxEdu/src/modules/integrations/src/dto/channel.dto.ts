import { Channel } from '../types/enums';

// Channel Connect Request
export class ChannelConnectRequest {
  channel: Channel;
  accountId: string;
  mode: 'NEW';
  metadata?: Record<string, any>;
}

// Channel Disconnect Request
export class ChannelDisconnectRequest {
  channel: Channel;
  accountId: string;
  reason: string;
}

// Channel Health Query
export class ChannelHealthQuery {
  accountId: string;
}