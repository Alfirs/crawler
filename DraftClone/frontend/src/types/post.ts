export type SlideTemplateId = 'cover' | 'insight' | 'steps' | 'cta';
export type SlideLayout = 'stacked' | 'split' | 'centered';
export type AspectRatio = 'portrait' | 'square' | 'story';
export type SlideContentField =
  | 'label'
  | 'title'
  | 'subtitle'
  | 'body'
  | 'bullets'
  | 'tags'
  | 'cta';

export interface EditorSettings {
  applyToAll?: boolean;
  typography?: { title: string; body: string };
  palette?: { background: string; text: string; accent: string };
  background?: {
    type: 'color' | 'gradient' | 'image';
    value?: string;
    gradient?: { from: string; to: string; angle?: number };
    imageUrl?: string | null;
  };
  backgroundLibrary?: {
    colors: string[];
    gradients: { id: string; name: string; from: string; to: string; angle?: number }[];
    images: string[];
  };
  brandKit?: {
    activeId: string;
    presets: Array<{
      id: string;
      name: string;
      palette: { background: string; text: string; accent: string };
      typography: { title: string; body: string };
      background?: {
        type: 'color' | 'gradient' | 'image';
        value?: string;
        gradient?: { from: string; to: string; angle?: number };
        imageUrl?: string | null;
      };
    }>;
  };
  aspect?: AspectRatio;
  [key: string]: any;
}

export interface Slide {
  id: string;
  index: number;
  templateId: SlideTemplateId;
  layout: SlideLayout;
  label?: string;
  title?: string;
  subtitle?: string;
  body?: string;
  bullets?: string[];
  tags?: string[];
  cta?: string;
  notes?: string;
  blocksOrder?: SlideContentField[];
}

export interface PostTheme {
  id: string;
  background: string;
  text: string;
  accent: string;
}

export interface TypographyPreset {
  id: string;
  headlineFont: string;
  bodyFont: string;
}

export interface Post {
  id: number;
  status: 'draft' | 'published' | 'ready';
  themeId: string;
  typographyId: string;
  aspect: AspectRatio;
  applyToAll: boolean;
  handle: string;
  slides: Slide[];
  settings?: EditorSettings;
  shareUrl?: string | null;
  token: string;
}
