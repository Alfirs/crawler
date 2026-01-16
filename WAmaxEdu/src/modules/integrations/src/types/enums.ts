export enum Channel {
  WHATSAPP = 'WHATSAPP',
  TELEGRAM = 'TELEGRAM',
}

export enum ConversationType {
  EXTERNAL_PARTICIPANT = 'EXTERNAL_PARTICIPANT',
  THREAD = 'THREAD',
}

export enum MessageKind {
  TEXT = 'TEXT',
  MEDIA = 'MEDIA',
  LOCATION = 'LOCATION',
  CONTACT = 'CONTACT',
  INTERACTIVE = 'INTERACTIVE',
  REACTION = 'REACTION',
}

export enum TextFormat {
  PLAIN = 'PLAIN',
  MARKDOWN = 'MARKDOWN',
  HTML = 'HTML',
}

export enum MediaType {
  IMAGE = 'IMAGE',
  VIDEO = 'VIDEO',
  AUDIO = 'AUDIO',
  FILE = 'FILE',
}

export enum InteractiveType {
  BUTTONS = 'BUTTONS',
  LIST = 'LIST',
}

export enum ButtonKind {
  REPLY = 'REPLY',
  URL = 'URL',
  CALL = 'CALL',
}

export enum ParticipantType {
  USER = 'USER',
  CONTACT = 'CONTACT',
  UNKNOWN = 'UNKNOWN',
}

export enum DeliveryStatus {
  PENDING = 'PENDING',
  SENT = 'SENT',
  DELIVERED = 'DELIVERED',
  READ = 'READ',
  FAILED = 'FAILED',
}

export enum ConnectionState {
  CONNECTED = 'CONNECTED',
  DISCONNECTED = 'DISCONNECTED',
  PENDING = 'PENDING',
  AWAITING_USER_ACTION = 'AWAITING_USER_ACTION',
  CONNECTING = 'CONNECTING',
  FAILED = 'FAILED',
}