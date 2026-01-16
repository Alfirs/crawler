import { usePost, useEditorStore } from '../../state/useEditorStore';
import { TYPOGRAPHY } from '../../constants/design';

const TextPanel = () => {
  const post = usePost();
  const setTypography = useEditorStore((state) => state.setTypography);
  if (!post) return null;

  return (
    <div className="typography-grid">
      {Object.entries(TYPOGRAPHY).map(([id, fonts]) => (
        <button
          key={id}
          className={id === post.typographyId ? 'typo-card active' : 'typo-card'}
          type="button"
          onClick={() => setTypography(id)}
        >
          <div className="typo-preview">
            <p style={{ fontFamily: fonts.headline }}>ГЛАВНЫЙ ЗАГОЛОВОК</p>
            <p style={{ fontFamily: fonts.body }}>Основной текст для карусели и заметок</p>
          </div>
          <strong>{fonts.label}</strong>
          <span>
            {fonts.headline} / {fonts.body}
          </span>
        </button>
      ))}
    </div>
  );
};

export default TextPanel;
