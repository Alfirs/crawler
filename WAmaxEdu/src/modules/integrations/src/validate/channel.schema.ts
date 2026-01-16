import { JSONSchema7 } from 'json-schema';

export const channelConnectSchema: JSONSchema7 = {
  $id: 'ChannelConnectRequest',
  type: 'object',
  properties: {
    channel: {
      type: 'string',
      enum: ['WHATSAPP']
    },
    accountId: {
      type: 'string',
      minLength: 1
    },
    mode: {
      type: 'string',
      enum: ['NEW']
    },
    metadata: {
      type: 'object'
    }
  },
  required: ['channel', 'accountId', 'mode']
};

export const channelDisconnectSchema: JSONSchema7 = {
  $id: 'ChannelDisconnectRequest',
  type: 'object',
  properties: {
    channel: {
      type: 'string',
      enum: ['WHATSAPP']
    },
    accountId: {
      type: 'string',
      minLength: 1
    },
    reason: {
      type: 'string',
      minLength: 1
    }
  },
  required: ['channel', 'accountId', 'reason']
};