import { create } from 'zustand';
import { EditorSettings, Post, Slide } from '../types/post';
import { TEMPLATE_MAP } from '../constants/templates';
import { THEMES, TYPOGRAPHY } from '../constants/design';

type Palette = { background: string; text: string; accent: string };
type FontPair = { title: string; body: string };

const randomId = () =>
  typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

const paletteForTheme = (themeId: string): Palette => THEMES[themeId] ?? THEMES.midnight;

const typographyForId = (typographyId: string): FontPair => {
  const fallback = TYPOGRAPHY[typographyId] ?? TYPOGRAPHY['montserrat-pt'];
  return {
    title: fallback.headline,
    body: fallback.body
  };
};

const ensureBackground = (
  current:
    | {
        type: 'color' | 'gradient' | 'image';
        value?: string;
        gradient?: { from: string; to: string; angle?: number };
        imageUrl?: string | null;
      }
    | undefined,
  palette: Palette
) =>
  current || {
    type: 'color',
    value: palette.background,
    gradient: undefined,
    imageUrl: null
  };

const ensureLibrary = (
  library:
    | {
        colors: string[];
        gradients: { id: string; name: string; from: string; to: string; angle?: number }[];
        images: string[];
      }
    | undefined,
  palette: Palette
) =>
  library || {
    colors: [palette.background],
    gradients: [],
    images: []
  };

const ensureBrandKit = (
  themeId: string,
  palette: Palette,
  typography: FontPair,
  brandKit?: EditorSettings['brandKit']
) => {
  if (brandKit?.presets?.length) {
    const presets = brandKit.presets.map((preset: any, index: number) => ({
      id: preset.id || `brand-${index}`,
      name: preset.name || `Preset ${index + 1}`,
      palette: preset.palette || palette,
      typography: preset.typography || typography,
      background: ensureBackground(preset.background, preset.palette || palette)
    }));
    return {
      activeId: brandKit.activeId || presets[0].id,
      presets
    };
  }
  return {
    activeId: 'brand-default',
    presets: [
      {
        id: 'brand-default',
        name: `${themeId} base`,
        palette,
        typography,
        background: ensureBackground(undefined, palette)
      }
    ]
  };
};

const normalizeSettings = (post: Post) => {
  const palette = post.settings?.palette || paletteForTheme(post.themeId);
  const typography = post.settings?.typography || typographyForId(post.typographyId);
  const background = ensureBackground(post.settings?.background, palette);
  const backgroundLibrary = ensureLibrary(post.settings?.backgroundLibrary, palette);
  const brandKit = ensureBrandKit(post.themeId, palette, typography, post.settings?.brandKit);
  return {
    ...(post.settings || {}),
    palette,
    typography,
    background,
    backgroundLibrary,
    brandKit,
    aspect: post.aspect
  };
};

type SlideField = keyof Pick<
  Slide,
  | 'label'
  | 'title'
  | 'subtitle'
  | 'body'
  | 'bullets'
  | 'tags'
  | 'cta'
  | 'notes'
  | 'layout'
  | 'templateId'
  | 'blocksOrder'
>;

interface EditorStore {
  post?: Post;
  currentSlideId?: string;
  history: Post[];
  future: Post[];
  dirty: boolean;
  revision: number;
  setPost: (post: Post) => void;
  setCurrentSlide: (slideId: string) => void;
  updateSlideField: (slideId: string, field: SlideField, value: Slide[SlideField]) => void;
  addSlide: () => void;
  duplicateSlide: (slideId: string) => void;
  deleteSlide: (slideId: string) => void;
  moveSlide: (slideId: string, offset: number) => void;
  applyTemplate: (slideId: string, templateId: Slide['templateId']) => void;
  setBlockOrder: (slideId: string, order: Slide['blocksOrder']) => void;
  setTheme: (themeId: string) => void;
  setTypography: (typographyId: string) => void;
  setPalette: (palette: Palette) => void;
  setBackground: (
    background: NonNullable<EditorSettings['background']>
  ) => void;
  saveBrandPreset: (name: string) => void;
  applyBrandPreset: (presetId: string) => void;
  setAspect: (aspect: Post['aspect']) => void;
  setApplyToAll: (value: boolean) => void;
  undo: () => void;
  redo: () => void;
  markSaved: () => void;
}

const reindexSlides = (slides: Slide[]): Slide[] =>
  slides.map((slide, idx) => ({ ...slide, index: idx }));

const clonePost = (post: Post): Post => JSON.parse(JSON.stringify(post));

export const useEditorStore = create<EditorStore>((set) => ({
  post: undefined,
  currentSlideId: undefined,
  history: [],
  future: [],
  dirty: false,
  revision: 0,
  setPost: (post) =>
    set(() => {
      const normalizedSlides = post.slides.map((slide, index) => {
        const template = TEMPLATE_MAP[slide.templateId];
        return {
          ...slide,
          index,
          blocksOrder: slide.blocksOrder || template?.order
        };
      });
      const normalizedSettings = normalizeSettings(post);
      return {
        post: {
          ...post,
          slides: normalizedSlides,
          settings: normalizedSettings
        },
        currentSlideId: normalizedSlides[0]?.id,
        history: [],
        future: [],
        dirty: false,
        revision: 0
      };
    }),
  setCurrentSlide: (slideId) =>
    set((state) => {
      if (!state.post) return state;
      return {
        currentSlideId: slideId
      };
    }),
  updateSlideField: (slideId, field, value) =>
    set((state) => {
      if (!state.post) return state;
      const history = state.post ? [...state.history, clonePost(state.post)] : state.history;
      const slides = state.post.slides.map((slide) =>
        slide.id === slideId ? { ...slide, [field]: value } : slide
      );
      return {
        post: { ...state.post, slides },
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  addSlide: () =>
    set((state) => {
      if (!state.post) return state;
      const history = [...state.history, clonePost(state.post)];
      const template = TEMPLATE_MAP['insight'];
      const newSlide: Slide = {
        id: crypto.randomUUID(),
        index: state.post.slides.length,
        templateId: 'insight',
        layout: 'stacked',
        title: '',
        subtitle: '',
        body: '',
        bullets: [],
        blocksOrder: template?.order
      };
      const slides = reindexSlides([...state.post.slides, newSlide]);
      return {
        post: { ...state.post, slides },
        currentSlideId: newSlide.id,
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  duplicateSlide: (slideId) =>
    set((state) => {
      if (!state.post) return state;
      const original = state.post.slides.find((slide) => slide.id === slideId);
      if (!original) return state;
      const history = [...state.history, clonePost(state.post)];
      const copy: Slide = { ...original, id: crypto.randomUUID() };
      const slides = reindexSlides(
        state.post.slides.flatMap((slide) =>
          slide.id === slideId ? [slide, copy] : [slide]
        )
      );
      return {
        post: { ...state.post, slides },
        currentSlideId: copy.id,
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  deleteSlide: (slideId) =>
    set((state) => {
      if (!state.post) return state;
      const history = [...state.history, clonePost(state.post)];
      const slides = state.post.slides.filter((slide) => slide.id !== slideId);
      if (!slides.length) {
        slides.push({
          id: crypto.randomUUID(),
          index: 0,
          templateId: 'insight',
          layout: 'stacked',
          bullets: []
        } as Slide);
      }
      return {
        post: { ...state.post, slides: reindexSlides(slides) },
        currentSlideId: slides[0].id,
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  moveSlide: (slideId, offset) =>
    set((state) => {
      if (!state.post) return state;
      const index = state.post.slides.findIndex((slide) => slide.id === slideId);
      const targetIndex = index + offset;
      if (index < 0 || targetIndex < 0 || targetIndex >= state.post.slides.length) {
        return state;
      }
      const history = [...state.history, clonePost(state.post)];
      const slides = [...state.post.slides];
      const [moved] = slides.splice(index, 1);
      slides.splice(targetIndex, 0, moved);
      return {
        post: { ...state.post, slides: reindexSlides(slides) },
        currentSlideId: moved.id,
        history,
        future: [],
        dirty: true
      };
    }),
  applyTemplate: (slideId, templateId) =>
    set((state) => {
      if (!state.post) return state;
      const template = TEMPLATE_MAP[templateId];
      if (!template) return state;
      const history = [...state.history, clonePost(state.post)];
      const slides = state.post.slides.map((slide) => {
        if (slide.id !== slideId) return slide;
        return {
          ...slide,
          templateId,
          layout: template.layout,
          ...template.defaults,
          blocksOrder: template.order
        };
      });
      return {
        post: { ...state.post, slides },
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  setBlockOrder: (slideId, order) =>
    set((state) => {
      if (!state.post) return state;
      const history = [...state.history, clonePost(state.post)];
      const slides = state.post.slides.map((slide) =>
        slide.id === slideId ? { ...slide, blocksOrder: order } : slide
      );
      return {
        post: { ...state.post, slides },
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  setTheme: (themeId) =>
    set((state) => {
      if (!state.post) return state;
      const palette = paletteForTheme(themeId);
      const typography =
        state.post.settings?.typography || typographyForId(state.post.typographyId);
      const background = ensureBackground(state.post.settings?.background, palette);
      const backgroundLibrary = ensureLibrary(state.post.settings?.backgroundLibrary, palette);
      const brandKit = ensureBrandKit(themeId, palette, typography, state.post.settings?.brandKit);
      const history = [...state.history, clonePost(state.post)];
      return {
        post: {
          ...state.post,
          themeId,
          settings: {
            ...(state.post.settings || {}),
            palette,
            background,
            backgroundLibrary,
            brandKit
          }
        },
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  setTypography: (typographyId) =>
    set((state) => {
      if (!state.post) return state;
      const fontPair = typographyForId(typographyId);
      const history = [...state.history, clonePost(state.post)];
      const existingSettings = state.post.settings || {};
      const activeId =
        existingSettings.brandKit?.activeId ||
        existingSettings.brandKit?.presets?.[0]?.id ||
        'brand-default';
      const updatedBrandKit = existingSettings.brandKit
        ? {
            ...existingSettings.brandKit,
            activeId,
            presets: existingSettings.brandKit.presets.map((preset) =>
              preset.id === activeId ? { ...preset, typography: fontPair } : preset
            )
          }
        : undefined;
      return {
        post: {
          ...state.post,
          typographyId,
          settings: {
            ...existingSettings,
            typography: fontPair,
            brandKit: updatedBrandKit || existingSettings.brandKit
          }
        },
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  setPalette: (palette) =>
    set((state) => {
      if (!state.post) return state;
      const history = [...state.history, clonePost(state.post)];
      const existingSettings = state.post.settings || {};
      const libraryBase = ensureLibrary(existingSettings.backgroundLibrary, palette);
      const colors = Array.from(new Set([...(libraryBase.colors || []), palette.background]));
      const activeId =
        existingSettings.brandKit?.activeId ||
        existingSettings.brandKit?.presets?.[0]?.id ||
        'brand-default';
      const updatedBrandKit = existingSettings.brandKit
        ? {
            ...existingSettings.brandKit,
            activeId,
            presets: existingSettings.brandKit.presets.map((preset) =>
              preset.id === activeId ? { ...preset, palette } : preset
            )
          }
        : undefined;
      return {
        post: {
          ...state.post,
          settings: {
            ...existingSettings,
            palette,
            brandKit: updatedBrandKit
              ? { ...updatedBrandKit, activeId: updatedBrandKit.activeId }
              : existingSettings.brandKit,
            backgroundLibrary: { ...libraryBase, colors }
          }
        },
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  setBackground: (background) =>
    set((state) => {
      if (!state.post) return state;
      const history = [...state.history, clonePost(state.post)];
      const existingSettings = state.post.settings || {};
      const palette = existingSettings.palette || paletteForTheme(state.post.themeId);
      const libraryBase = ensureLibrary(existingSettings.backgroundLibrary, palette);
      let gradients = libraryBase.gradients || [];
      let images = libraryBase.images || [];
      if (background.type === 'gradient' && background.gradient) {
        const id = `${background.gradient.from}-${background.gradient.to}-${background.gradient.angle ?? 0}`;
        if (!gradients.find((item) => item.id === id)) {
          gradients = [
            ...gradients,
            {
              id,
              name: `Custom ${gradients.length + 1}`,
              ...background.gradient
            }
          ];
        }
      }
      if (background.type === 'image' && background.imageUrl) {
        if (!images.includes(background.imageUrl)) {
          images = [...images, background.imageUrl];
        }
      }
      const activeId =
        existingSettings.brandKit?.activeId ||
        existingSettings.brandKit?.presets?.[0]?.id ||
        'brand-default';
      const updatedBrandKit = existingSettings.brandKit
        ? {
            ...existingSettings.brandKit,
            activeId,
            presets: existingSettings.brandKit.presets.map((preset) =>
              preset.id === activeId ? { ...preset, background } : preset
            )
          }
        : undefined;
      return {
        post: {
          ...state.post,
          settings: {
            ...existingSettings,
            background,
            brandKit: updatedBrandKit || existingSettings.brandKit,
            backgroundLibrary: { ...libraryBase, gradients, images }
          }
        },
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  saveBrandPreset: (name) =>
    set((state) => {
      if (!state.post) return state;
      const history = [...state.history, clonePost(state.post)];
      const existingSettings = state.post.settings || {};
      const palette = existingSettings.palette || paletteForTheme(state.post.themeId);
      const typography = existingSettings.typography || typographyForId(state.post.typographyId);
      const background = ensureBackground(existingSettings.background, palette);
      const normalizedKit = ensureBrandKit(
        state.post.themeId,
        palette,
        typography,
        existingSettings.brandKit
      );
      const presetId = randomId();
      const presetName = name.trim() || `Preset ${normalizedKit.presets.length + 1}`;
      const updatedKit = {
        activeId: presetId,
        presets: [
          ...normalizedKit.presets,
          {
            id: presetId,
            name: presetName,
            palette,
            typography,
            background
          }
        ]
      };
      return {
        post: {
          ...state.post,
          settings: {
            ...existingSettings,
            brandKit: updatedKit
          }
        },
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  applyBrandPreset: (presetId) =>
    set((state) => {
      if (!state.post || !state.post.settings?.brandKit) return state;
      const preset = state.post.settings.brandKit.presets.find((item) => item.id === presetId);
      if (!preset) return state;
      const history = [...state.history, clonePost(state.post)];
      const palette = preset.palette || paletteForTheme(state.post.themeId);
      const background = ensureBackground(preset.background, palette);
      const typography = preset.typography || state.post.settings.typography;
      return {
        post: {
          ...state.post,
          settings: {
            ...(state.post.settings || {}),
            palette,
            background,
            typography: typography || state.post.settings?.typography,
            brandKit: {
              ...state.post.settings.brandKit,
              activeId: presetId
            }
          }
        },
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  setAspect: (aspect) =>
    set((state) => {
      if (!state.post) return state;
      const history = [...state.history, clonePost(state.post)];
      return {
        post: {
          ...state.post,
          aspect,
          settings: { ...(state.post.settings || {}), aspect }
        },
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  setApplyToAll: (value) =>
    set((state) => {
      if (!state.post) return state;
      const history = [...state.history, clonePost(state.post)];
      return {
        post: { ...state.post, applyToAll: value },
        history,
        future: [],
        dirty: true,
        revision: state.revision + 1
      };
    }),
  undo: () =>
    set((state) => {
      if (!state.post || state.history.length === 0) return state;
      const previous = state.history[state.history.length - 1];
      const history = state.history.slice(0, -1);
      const future = [clonePost(state.post), ...state.future];
      return {
        post: previous,
        currentSlideId: previous.slides[0]?.id,
        history,
        future,
        dirty: true
      };
    }),
  redo: () =>
    set((state) => {
      if (!state.post || state.future.length === 0) return state;
      const next = state.future[0];
      const future = state.future.slice(1);
      const history = [...state.history, clonePost(state.post)];
      return {
        post: next,
        currentSlideId: next.slides[0]?.id,
        history,
        future,
        dirty: true
      };
    }),
  markSaved: () =>
    set((state) => {
      if (!state.post) return state;
      return { ...state, dirty: false };
    })
}));

export const usePost = () => useEditorStore((state) => state.post);

export const useCurrentSlide = () =>
  useEditorStore((state) => {
    const slide =
      state.post?.slides.find((item) => item.id === state.currentSlideId) ||
      state.post?.slides[0];
    return slide;
  });
