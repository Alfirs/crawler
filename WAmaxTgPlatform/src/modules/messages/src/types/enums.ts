export enum Direction {
  INBOUND = 'INBOUND',
  OUTBOUND = 'OUTBOUND'
}

export enum DeliveryStatus {
  PENDING = 'PENDING',
  SENT = 'SENT',
  DELIVERED = 'DELIVERED',
  READ = 'READ',
  FAILED = 'FAILED'
}

export enum ParticipantType {
  USER = 'USER',
  CONTACT = 'CONTACT',
  UNKNOWN = 'UNKNOWN'
}

// Re-export from integrations for consistency
export { Channel, ConversationType, MessageKind } from '@integrations/types/enums';
