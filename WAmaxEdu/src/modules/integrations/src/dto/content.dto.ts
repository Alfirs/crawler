import { TextFormat, MediaType, InteractiveType, ButtonKind } from '../types/enums';

// Text Content
export class TextContent {
  text: string;
  format: TextFormat;
}

// Media Content
export class MediaSource {
  url?: string;
  fileId?: string;
}

export class MediaThumbnail {
  url?: string;
  fileId?: string;
}

export class MediaContent {
  mediaType: MediaType;
  source: MediaSource;
  caption?: string;
  filename?: string;
  mimeType?: string;
  sizeBytes?: number;
  thumbnail?: MediaThumbnail;
}

// Location Content
export class LocationContent {
  latitude: number;
  longitude: number;
  address?: string;
  title?: string;
}

// Contact Content
export class Phone {
  number: string;
  label?: string;
}

export class Email {
  email: string;
  label?: string;
}

export class Organization {
  company?: string;
  title?: string;
}

export class Contact {
  displayName: string;
  phones: Phone[];
  emails?: Email[];
  organization?: Organization;
}

export class ContactContent {
  contacts: Contact[];
}

// Interactive Content
export class Button {
  actionId: string;
  title: string;
  payload?: any;
  kind: ButtonKind;
  url?: string; // only if kind=URL
  phone?: string; // only if kind=CALL
}

export class InteractiveButtons {
  buttons: Button[];
}

export class ListItem {
  actionId: string;
  title: string;
  description?: string;
  payload?: any;
}

export class ListSection {
  title?: string;
  items: ListItem[];
}

export class InteractiveList {
  buttonTitle: string;
  sections: ListSection[];
}

export class InteractiveContent {
  interactiveType: InteractiveType;
  bodyText: string;
  footerText?: string;
  actions: InteractiveButtons | InteractiveList;
}

// Reaction Content
export class ReactionContent {
  targetMessageId: string;
  reaction: string;
}