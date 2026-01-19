import { ConversationType, ParticipantType } from '../types/enums';

// Common types for events
export interface ConversationRef {
  type: ConversationType;
  id: string;
}

export interface ParticipantRef {
  type: ParticipantType;
  id: string;
}

// Message content types (same as DTOs)
export type MessageContent =
  | TextContent
  | MediaContent
  | LocationContent
  | ContactContent
  | InteractiveContent
  | ReactionContent;

export interface TextContent {
  text: string;
  format: string;
}

export interface MediaContent {
  mediaType: string;
  source: {
    url?: string;
    fileId?: string;
  };
  caption?: string;
  filename?: string;
  mimeType?: string;
  sizeBytes?: number;
  thumbnail?: {
    url?: string;
    fileId?: string;
  };
}

export interface LocationContent {
  latitude: number;
  longitude: number;
  address?: string;
  title?: string;
}

export interface ContactContent {
  contacts: Array<{
    displayName: string;
    phones: Array<{
      number: string;
      label?: string;
    }>;
    emails?: Array<{
      email: string;
      label?: string;
    }>;
    organization?: {
      company?: string;
      title?: string;
    };
  }>;
}

export interface InteractiveContent {
  interactiveType: string;
  bodyText: string;
  footerText?: string;
  actions: any; // Buttons or List
}

export interface ReactionContent {
  targetMessageId: string;
  reaction: string;
}