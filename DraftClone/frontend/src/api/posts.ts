import { Post, Slide } from '../types/post';
import { TYPOGRAPHY } from '../constants/design';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

type PostEditorResponse = {
  id: number;
  status: string;
  theme?: string;
  share_url?: string | null;
  data?: {
    slides?: Slide[];
    settings?: Record<string, any>;
  };
};

const makeId = () =>
  typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

const normalizeSlides = (slides: any[] = []): Slide[] =>
  slides.map((slide, index) => ({
    id: slide.id || makeId(),
    index,
    templateId: slide.templateId || 'insight',
    layout: slide.layout || 'stacked',
    label: slide.label,
    title: slide.title,
    subtitle: slide.subtitle,
    body: slide.body,
    bullets: slide.bullets || [],
    tags: slide.tags || [],
    cta: slide.cta,
    notes: slide.notes,
    blocksOrder: slide.blocksOrder
  }));

const detectTypographyId = (settings: any): string => {
  const typography = settings?.typography;
  if (!typography) return 'montserrat-pt';
  const entry = Object.entries(TYPOGRAPHY).find(
    ([, preset]) => preset.headline === typography.title && preset.body === typography.body
  );
  return entry?.[0] ?? 'montserrat-pt';
};

const transformResponse = (raw: PostEditorResponse, token: string): Post => {
  const slides = normalizeSlides(raw.data?.slides ?? []);
  const settings = raw.data?.settings ?? {};
  const themeId = raw.theme ?? (settings.theme as string) ?? 'midnight';
  const typographyId = detectTypographyId(settings);
  const aspect = (settings.aspect as Post['aspect']) || 'portrait';
  const applyToAll = settings.applyToAll ?? true;
  return {
    id: raw.id,
    status: (raw.status as Post['status']) ?? 'draft',
    themeId,
    typographyId,
    aspect,
    applyToAll,
    handle: '@draftclone',
    slides,
    settings,
    shareUrl: raw.share_url ?? null,
    token
  };
};

export async function fetchPost(postId: number, token: string): Promise<Post> {
  const res = await fetch(
    `${API_URL}/api/posts/${postId}/editor?token=${encodeURIComponent(token)}`
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch post ${postId}`);
  }
  const raw = (await res.json()) as PostEditorResponse;
  return transformResponse(raw, token);
}

export async function savePost(post: Post): Promise<Post> {
  const typography = TYPOGRAPHY[post.typographyId] ?? TYPOGRAPHY['montserrat-pt'];
  const mapFont = (value: string) =>
    value ? value.split(',')[0].replace(/["']/g, '').trim() : value;
  const settingsPayload = {
    ...(post.settings || {}),
    applyToAll: post.applyToAll,
    aspect: post.aspect,
    typography: {
      title: mapFont(typography.headline),
      body: mapFont(typography.body)
    }
  };
  const payload = {
    slides: post.slides.map(({ id, index, ...rest }) => rest),
    settings: settingsPayload,
    theme: post.themeId
  };
  const res = await fetch(
    `${API_URL}/api/posts/${post.id}?token=${encodeURIComponent(post.token)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }
  );
  if (!res.ok) {
    throw new Error('Failed to save post');
  }
  const raw = (await res.json()) as PostEditorResponse;
  return transformResponse(raw, post.token);
}

export async function exportPost(
  post: Post,
  options: { format: 'png' | 'pdf'; range: 'all' | 'current' }
): Promise<string> {
  const res = await fetch(
    `${API_URL}/api/posts/${post.id}/export?token=${encodeURIComponent(post.token)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options)
    }
  );
  if (!res.ok) {
    throw new Error('Failed to start export');
  }
  const data = await res.json();
  return data.detail || 'Export requested';
}

export async function runAiAction(
  post: Post,
  options: { field: 'title' | 'subtitle' | 'body' | 'cta'; action: string; value: string }
): Promise<string> {
  const res = await fetch(
    `${API_URL}/api/posts/${post.id}/ai?token=${encodeURIComponent(post.token)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options)
    }
  );
  if (!res.ok) {
    throw new Error('AI action failed');
  }
  const data = await res.json();
  return data.value;
}

export function buildShareLink(postId: number, token: string): string {
  const base = API_URL.replace(/\/$/, '');
  return `${base}/posts/${postId}/editor?token=${token}`;
}

export async function uploadBackgroundImage(post: Post, file: File): Promise<string> {
  const body = new FormData();
  body.append('file', file);
  const res = await fetch(
    `${API_URL}/api/posts/${post.id}/background-image?token=${encodeURIComponent(post.token)}`,
    {
      method: 'POST',
      body
    }
  );
  if (!res.ok) {
    throw new Error('Upload failed');
  }
  const data = await res.json();
  return data.url as string;
}
