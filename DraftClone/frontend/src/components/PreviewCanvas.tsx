import { useEffect, useState, type MouseEvent } from 'react';
import { useCurrentSlide, useEditorStore, usePost } from '../state/useEditorStore';
import { TEMPLATE_MAP } from '../constants/templates';
import { THEMES } from '../constants/design';
import type { SlideContentField } from '../types/post';

type PreviewCanvasProps = {
  aiHighlightField?: 'title' | 'subtitle' | 'body' | 'cta' | null;
  zoom?: number;
};

const ASPECT_PADDING: Record<string, number> = {
  portrait: 132,
  square: 100,
  story: 178
};

const PreviewCanvas = ({ aiHighlightField, zoom = 1 }: PreviewCanvasProps) => {
  const post = usePost();
  const slide = useCurrentSlide();
  const updateSlideField = useEditorStore((state) => state.updateSlideField);
  const setBlockOrder = useEditorStore((state) => state.setBlockOrder);
  const setCurrentSlide = useEditorStore((state) => state.setCurrentSlide);
  const [context, setContext] = useState<{ field: SlideContentField; x: number; y: number } | null>(
    null
  );
  const [dragField, setDragField] = useState<SlideContentField | null>(null);

  useEffect(() => {
    const handler = () => setContext(null);
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, []);

  if (!post || !slide) {
    return (
      <section className="panel preview-panel empty">
        <p>Выберите слайд, чтобы начать редактирование.</p>
      </section>
    );
  }

  const template = TEMPLATE_MAP[slide.templateId] || TEMPLATE_MAP.cover;
  const palette = post.settings?.palette ?? THEMES[post.themeId] ?? THEMES.midnight;
  const typography = post.settings?.typography;
  const background = post.settings?.background;
  const aspectPadding = ASPECT_PADDING[post.aspect] ?? ASPECT_PADDING.portrait;

  const baseOrder =
    (slide.blocksOrder && slide.blocksOrder.length > 0 ? slide.blocksOrder : template.order) ??
    template.order;
  const visibleOrder = baseOrder.filter((field) => template.fields?.[field]);

  const blockClasses = (field: SlideContentField) => {
    const classes = ['canvas-block', `field-${field}`];
    if (aiHighlightField === field) classes.push('ai-highlight');
    if (dragField === field) classes.push('dragging');
    return classes.join(' ');
  };

  const backgroundStyle = (() => {
    if (!background) {
      return { background: palette.background };
    }
    if (background.type === 'gradient' && background.gradient) {
      return {
        background: `linear-gradient(${background.gradient.angle ?? 135}deg, ${
          background.gradient.from
        }, ${background.gradient.to})`
      };
    }
    if (background.type === 'image' && background.imageUrl) {
      return {
        backgroundImage: `url(${background.imageUrl})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center'
      };
    }
    return { background: background.value ?? palette.background };
  })();

  const handleInlineChange = (field: SlideContentField, value: string) => {
    updateSlideField(slide.id, field, value);
  };

  const handleBulletChange = (index: number, value: string) => {
    const bullets = [...(slide.bullets ?? [])];
    bullets[index] = value;
    updateSlideField(slide.id, 'bullets', bullets);
  };

  const handleTagChange = (index: number, value: string) => {
    const tags = [...(slide.tags ?? [])];
    tags[index] = value;
    updateSlideField(slide.id, 'tags', tags);
  };

  const handleAddBullet = () => {
    const bullets = [...(slide.bullets ?? []), 'Новый пункт'];
    updateSlideField(slide.id, 'bullets', bullets);
  };

  const handleAddTag = () => {
    const tags = [...(slide.tags ?? []), 'Новый тег'];
    updateSlideField(slide.id, 'tags', tags);
  };

  const handleRemoveBullet = (index: number) => {
    const bullets = [...(slide.bullets ?? [])];
    bullets.splice(index, 1);
    updateSlideField(slide.id, 'bullets', bullets);
  };

  const handleRemoveTag = (index: number) => {
    const tags = [...(slide.tags ?? [])];
    tags.splice(index, 1);
    updateSlideField(slide.id, 'tags', tags);
  };

  const openContextMenu = (field: SlideContentField, event: MouseEvent) => {
    event.stopPropagation();
    setContext({ field, x: event.clientX, y: event.clientY });
  };

  const applyContextAction = (action: 'uppercase' | 'lowercase' | 'clear') => {
    if (!context) return;
    const currentValue = (slide[context.field] as string) || '';
    if (action === 'uppercase') {
      handleInlineChange(context.field, currentValue.toUpperCase());
    } else if (action === 'lowercase') {
      handleInlineChange(context.field, currentValue.toLowerCase());
    } else if (action === 'clear') {
      handleInlineChange(context.field, '');
    }
    setContext(null);
  };

  const reorderBlocks = (targetField: SlideContentField) => {
    if (!dragField || dragField === targetField) return;
    const base = [...visibleOrder];
    const fromIndex = base.indexOf(dragField);
    const toIndex = base.indexOf(targetField);
    if (fromIndex === -1 || toIndex === -1) return;
    const updated = [...base];
    const [removed] = updated.splice(fromIndex, 1);
    updated.splice(toIndex, 0, removed);
    setBlockOrder(slide.id, updated);
    setDragField(null);
  };

  const goToSlide = (offset: number) => {
    if (!post) return;
    const currentIndex = post.slides.findIndex((item) => item.id === slide.id);
    const nextIndex = currentIndex + offset;
    if (nextIndex < 0 || nextIndex >= post.slides.length) return;
    setCurrentSlide(post.slides[nextIndex].id);
  };

  const renderBlock = (field: SlideContentField) => {
    if (!template.fields?.[field]) return null;
    if (field === 'bullets') {
      const bullets = slide.bullets?.length ? slide.bullets : ['Добавьте буллет'];
      return (
        <div
          key={field}
          className={blockClasses(field)}
          draggable
          onDragStart={() => setDragField(field)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={() => reorderBlocks(field)}
          onDragEnd={() => setDragField(null)}
        >
          <span className="block-grip" aria-hidden="true">
            ⋮⋮
          </span>
          <ul className="canvas-bullets">
            {bullets.map((bullet, index) => (
              <li key={`${field}-${index}`}>
                <span
                  contentEditable
                  suppressContentEditableWarning
                  data-placeholder="Новый пункт"
                  onInput={(event) =>
                    handleBulletChange(index, event.currentTarget.textContent || '')
                  }
                >
                  {bullet}
                </span>
                {slide.bullets && slide.bullets.length > 1 && (
                  <button type="button" className="tiny" onClick={() => handleRemoveBullet(index)}>
                    ✕
                  </button>
                )}
              </li>
            ))}
          </ul>
          <button type="button" className="inline-add" onClick={handleAddBullet}>
            + Bullet
          </button>
        </div>
      );
    }

    if (field === 'tags') {
      const tags = slide.tags ?? [];
      return (
        <div
          key={field}
          className={blockClasses(field)}
          draggable
          onDragStart={() => setDragField(field)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={() => reorderBlocks(field)}
          onDragEnd={() => setDragField(null)}
        >
          <span className="block-grip" aria-hidden="true">
            ⋮⋮
          </span>
          <div className="canvas-tags">
            {tags.map((tag, index) => (
              <span key={`${field}-${index}`} className="canvas-tag">
                <span
                  contentEditable
                  suppressContentEditableWarning
                  data-placeholder="Tag"
                  onInput={(event) =>
                    handleTagChange(index, event.currentTarget.textContent || '')
                  }
                >
                  {tag}
                </span>
                <button type="button" onClick={() => handleRemoveTag(index)}>
                  ✕
                </button>
              </span>
            ))}
            <button type="button" className="inline-add" onClick={handleAddTag}>
              + Tag
            </button>
          </div>
        </div>
      );
    }

    const placeholders: Record<SlideContentField, string> = {
      label: 'Label',
      title: 'Заголовок',
      subtitle: 'Подзаголовок',
      body: 'Основной текст',
      bullets: '',
      tags: '',
      cta: 'CTA / Footer'
    };
    const value = (slide[field] as string) || '';

    return (
      <div
        key={field}
        className={blockClasses(field)}
        draggable
        onDragStart={() => setDragField(field)}
        onDragOver={(event) => event.preventDefault()}
        onDrop={() => reorderBlocks(field)}
        onDragEnd={() => setDragField(null)}
      >
        <span className="block-grip" aria-hidden="true">
          ⋮⋮
        </span>
        <button type="button" className="block-menu" onClick={(event) => openContextMenu(field, event)}>
          ⋯
        </button>
        <div
          className={`canvas-field ${field}`}
          contentEditable
          suppressContentEditableWarning
          data-placeholder={placeholders[field]}
          onInput={(event) => handleInlineChange(field, event.currentTarget.textContent || '')}
          style={{
            fontFamily: field === 'title' && typography?.title ? typography.title : undefined
          }}
        >
          {value}
        </div>
      </div>
    );
  };

  return (
    <section className="panel preview-panel">
      <div className="canvas-shell" style={{ transform: `scale(${zoom})` }}>
        <div className="canvas" style={{ ...backgroundStyle, paddingTop: `${aspectPadding}%` }}>
          <div className="canvas-safe" style={{ color: palette.text, fontFamily: typography?.body }}>
          <div className="canvas-meta">
            <span className="canvas-handle">{post.handle}</span>
            <span className="canvas-layout">{slide.layout}</span>
          </div>
          {visibleOrder.map((field) => renderBlock(field))}
          </div>
        </div>
      </div>
      <div className="canvas-tools">
        <button type="button" onClick={() => goToSlide(-1)}>
          ← Предыдущий
        </button>
        <button type="button" onClick={() => goToSlide(1)}>
          Следующий →
        </button>
      </div>
      {context && (
        <div
          className="canvas-context"
          style={{ top: context.y, left: context.x }}
          onClick={(event) => event.stopPropagation()}
        >
          <button type="button" onClick={() => applyContextAction('uppercase')}>
            Uppercase
          </button>
          <button type="button" onClick={() => applyContextAction('lowercase')}>
            Lowercase
          </button>
          <button type="button" onClick={() => applyContextAction('clear')}>
            Clear
          </button>
        </div>
      )}
    </section>
  );
};

export default PreviewCanvas;
