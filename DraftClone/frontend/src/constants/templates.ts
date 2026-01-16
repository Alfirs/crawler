import { Slide, SlideContentField } from '../types/post';

export type TemplateConfig = {
  id: Slide['templateId'];
  label: string;
  description: string;
  layout: Slide['layout'];
  fields: Partial<Record<SlideContentField, boolean>>;
  defaults?: Partial<Slide>;
  order?: SlideContentField[];
};

const BASE_ORDER: SlideContentField[] = [
  'label',
  'title',
  'subtitle',
  'body',
  'bullets',
  'tags',
  'cta'
];

export const TEMPLATE_CONFIGS: TemplateConfig[] = [
  {
    id: 'cover',
    label: 'Cover',
    description: 'Title + subtitle + CTA',
    layout: 'centered',
    fields: { label: true, title: true, subtitle: true, tags: true, cta: true },
    defaults: {
      label: 'New drop',
      title: 'Заголовок презентации',
      subtitle: 'Подзаголовок, объясняющий ценность предложения',
      cta: 'Подпишись →',
      tags: ['Tutorial']
    },
    order: ['label', 'title', 'subtitle', 'tags', 'cta']
  },
  {
    id: 'insight',
    label: 'Insight',
    description: 'Title + main copy',
    layout: 'stacked',
    fields: { label: true, title: true, body: true, tags: true, cta: true },
    defaults: {
      label: 'Insight',
      tags: ['Carousel']
    },
    order: BASE_ORDER
  },
  {
    id: 'steps',
    label: 'Steps',
    description: 'Title + bullet list',
    layout: 'stacked',
    fields: { label: true, title: true, bullets: true, body: true, tags: true, cta: true },
    defaults: {
      label: 'How-to',
      bullets: ['Шаг 1', 'Шаг 2', 'Шаг 3'],
      tags: ['Guide']
    },
    order: ['label', 'title', 'bullets', 'body', 'tags', 'cta']
  },
  {
    id: 'cta',
    label: 'CTA',
    description: 'Call-to-action',
    layout: 'centered',
    fields: { label: true, title: true, subtitle: true, body: true, cta: true, tags: true },
    defaults: {
      label: 'CTA',
      title: 'Готовы начать?',
      body: 'Оставьте заявку и получите чек-лист по запуску',
      cta: 'Перейти по ссылке',
      tags: ['Follow']
    },
    order: ['label', 'title', 'subtitle', 'body', 'cta', 'tags']
  }
];

export const TEMPLATE_MAP = Object.fromEntries(
  TEMPLATE_CONFIGS.map((tpl) => [tpl.id, { ...tpl, order: tpl.order || BASE_ORDER }])
);
