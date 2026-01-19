import { DeliveryStatus } from '../types/enums';

// Outbound Send Response
export class OutboundSendResponse {
  deliveryRequestId: string;
  status: DeliveryStatus;
}

// Channel Connect Response
export class ChannelConnectResponse {
  connectRequestId: string;
  state: string;
}

// Channel Disconnect Response
export class ChannelDisconnectResponse {
  state: string;
}

// Channel Health Response
export class ChannelHealthResponse {
  channel: string;
  accountId: string;
  connectionState: string;
  lastSeenAt: string;
  details: Record<string, any>;
}

// Error Response
export class ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: any;
  };
}