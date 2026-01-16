import { ChangeEvent } from 'react';
import { useCurrentSlide, useEditorStore, usePost } from '../state/useEditorStore';
import { TEMPLATE_MAP } from '../constants/templates';
import AIActionBar from './AIActionBar';

type InspectorProps = {
  onAiAction: (payload: { field: 'title' | 'subtitle' | 'body' | 'cta'; action: string }) => void;
  aiRunning?: boolean;
  aiLastAction?: string | null;
  highlightField?: 'title' | 'subtitle' | 'body' | 'cta' | null;
};

const InspectorPanel = ({ onAiAction, aiRunning, aiLastAction, highlightField }: InspectorProps) => {
  const slide = useCurrentSlide();
  const updateSlideField = useEditorStore((state) => state.updateSlideField);
  const post = usePost();
  const setApplyToAll = useEditorStore((state) => state.setApplyToAll);

  if (!slide) return null;

  const template = TEMPLATE_MAP[slide.templateId];
  const fieldEnabled = (field: keyof typeof template.fields) => template?.fields[field] ?? true;

  const handleChange =
    (field: 'label' | 'title' | 'subtitle' | 'body' | 'cta' | 'notes') =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      updateSlideField(slide.id, field, event.target.value);
    };

  const handleBulletChange = (index: number, value: string) => {
    const bullets = [...(slide.bullets || [])];
    bullets[index] = value;
    updateSlideField(slide.id, 'bullets', bullets);
  };

  const addBullet = () => {
    const bullets = [...(slide.bullets || []), ''];
    updateSlideField(slide.id, 'bullets', bullets);
  };

  const removeBullet = (index: number) => {
    const bullets = [...(slide.bullets || [])];
    bullets.splice(index, 1);
    updateSlideField(slide.id, 'bullets', bullets);
  };

  const addTag = () => {
    const tags = [...(slide.tags || []), 'Новый тег'];
    updateSlideField(slide.id, 'tags', tags);
  };

  const handleTagChange = (index: number, value: string) => {
    const tags = [...(slide.tags || [])];
    tags[index] = value;
    updateSlideField(slide.id, 'tags', tags);
  };

  const removeTag = (index: number) => {
    const tags = [...(slide.tags || [])];
    tags.splice(index, 1);
    updateSlideField(slide.id, 'tags', tags);
  };

  return (
    <section className="panel inspector-panel">
      <header className="panel-header">
        <h2>Edit slide</h2>
        <span>{slide.templateId}</span>
      </header>
      <label className={!fieldEnabled('label') ? 'field-disabled' : undefined}>
        Label
        <input value={slide.label || ''} onChange={handleChange('label')} disabled={!fieldEnabled('label')} />
      </label>
      <label
        className={[
          !fieldEnabled('title') && 'field-disabled',
          highlightField === 'title' && 'ai-highlight'
        ]
          .filter(Boolean)
          .join(' ')}
      >
        Title
        <input
          value={slide.title || ''}
          onChange={handleChange('title')}
          disabled={!fieldEnabled('title')}
        />
      </label>
      <label
        className={[
          !fieldEnabled('subtitle') && 'field-disabled',
          highlightField === 'subtitle' && 'ai-highlight'
        ]
          .filter(Boolean)
          .join(' ')}
      >
        Subtitle
        <input
          value={slide.subtitle || ''}
          onChange={handleChange('subtitle')}
          disabled={!fieldEnabled('subtitle')}
        />
      </label>
      <label
        className={[
          !fieldEnabled('cta') && 'field-disabled',
          highlightField === 'cta' && 'ai-highlight'
        ]
          .filter(Boolean)
          .join(' ')}
      >
        CTA / Footer
        <input value={slide.cta || ''} onChange={handleChange('cta')} disabled={!fieldEnabled('cta')} />
      </label>
      <label
        className={[
          !fieldEnabled('body') && 'field-disabled',
          highlightField === 'body' && 'ai-highlight'
        ]
          .filter(Boolean)
          .join(' ')}
      >
        Main text
        <textarea
          value={slide.body || ''}
          onChange={handleChange('body')}
          rows={4}
          disabled={!fieldEnabled('body')}
        />
      </label>
      {fieldEnabled('body') && (
        <AIActionBar
          onAction={(actionId) => onAiAction({ field: 'body', action: actionId })}
          isRunning={aiRunning}
          lastAction={aiLastAction}
        />
      )}
      {fieldEnabled('bullets') && (
        <div className="bullets-block">
          <div className="panel-header">
            <h3>Bullets</h3>
            <button type="button" onClick={addBullet}>
              + Bullet
            </button>
          </div>
          <div className="bullets-list">
            {(slide.bullets || []).map((bullet, index) => (
              <div key={index} className="bullet-item">
                <input value={bullet} onChange={(e) => handleBulletChange(index, e.target.value)} />
                <button type="button" onClick={() => removeBullet(index)}>×</button>
              </div>
            ))}
          </div>
        </div>
      )}
      {fieldEnabled('tags') && (
        <div className="tags-block">
          <div className="panel-header">
            <h3>Tags</h3>
            <button type="button" onClick={addTag}>
              + Tag
            </button>
          </div>
          <div className="tags-list">
            {(slide.tags || []).map((tag, index) => (
              <div key={index} className="tag-item">
                <input value={tag} onChange={(event) => handleTagChange(index, event.target.value)} />
                <button type="button" onClick={() => removeTag(index)}>×</button>
              </div>
            ))}
            {(!slide.tags || slide.tags.length === 0) && (
              <p className="muted">Добавьте теги вроде #case-study, Tips, Growth.</p>
            )}
          </div>
        </div>
      )}
      <label className="apply-all">
        <input
          type="checkbox"
          checked={post?.applyToAll ?? true}
          onChange={(e) => setApplyToAll(e.target.checked)}
        />
        Apply typography/background changes to all slides
      </label>
      <label>
        Notes
        <textarea value={slide.notes || ''} onChange={handleChange('notes')} rows={3} />
      </label>
    </section>
  );
};

export default InspectorPanel;
