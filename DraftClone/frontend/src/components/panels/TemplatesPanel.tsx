import { useCurrentSlide, useEditorStore, usePost } from '../../state/useEditorStore';
import { TEMPLATE_CONFIGS } from '../../constants/templates';
import { THEMES } from '../../constants/design';

const TemplatesPanel = () => {
  const slide = useCurrentSlide();
  const post = usePost();
  const applyTemplate = useEditorStore((state) => state.applyTemplate);
  if (!slide) return null;
  const palette = post ? THEMES[post.themeId] ?? THEMES.midnight : THEMES.midnight;

  return (
    <div className="template-grid">
      {TEMPLATE_CONFIGS.map((option) => {
        const isActive = option.id === slide.templateId;
        const defaults = option.defaults || {};
        return (
          <button
            key={option.id}
            type="button"
            className={isActive ? 'template-card active' : 'template-card'}
            onClick={() => applyTemplate(slide.id, option.id)}
          >
            <div className="template-preview" style={{ background: palette.background, color: palette.text }}>
              <span className="template-handle">{post?.handle ?? '@draftclone'}</span>
              <div className="template-label">{defaults.label ?? option.label}</div>
              {option.fields.title && <h3>{defaults.title ?? 'Заголовок здесь'}</h3>}
              {option.fields.subtitle && (
                <p className="template-subtitle">{defaults.subtitle ?? 'Подзаголовок с дополнительным текстом'}</p>
              )}
              {option.fields.body && (
                <p className="template-body">{defaults.body ?? 'Короткий текст для пояснения ключевой идеи.'}</p>
              )}
              {option.fields.bullets && (
                <ul>
                  {(defaults.bullets ?? ['Пункт 1', 'Пункт 2']).slice(0, 3).map((text, index) => (
                    <li key={`${option.id}-bullet-${index}`}>{text}</li>
                  ))}
                </ul>
              )}
              {option.fields.cta && <span className="template-cta">{defaults.cta ?? 'Follow me →'}</span>}
            </div>
            <div className="template-meta">
              <strong>{option.label}</strong>
              <span>{option.description}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
};

export default TemplatesPanel;
