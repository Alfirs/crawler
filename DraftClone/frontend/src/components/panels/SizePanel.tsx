import { usePost, useEditorStore } from '../../state/useEditorStore';

const sizes = [
  { id: 'portrait', label: '1080×1350', description: 'Instagram portrait' },
  { id: 'square', label: '1080×1080', description: 'Square format' },
  { id: 'story', label: '1080×1920', description: 'Story / Reels cover' }
];

const SizePanel = () => {
  const post = usePost();
  const setAspect = useEditorStore((state) => state.setAspect);
  if (!post) return null;

  return (
    <section className="tab-panel">
      <p className="muted">Соотношение сторон canvas.</p>
      <div className="chip-group">
        {sizes.map((size) => (
          <button
            key={size.id}
            className={size.id === post.aspect ? 'chip active' : 'chip'}
            type="button"
            onClick={() => setAspect(size.id as typeof post.aspect)}
          >
            <strong>{size.label}</strong>
            <span>{size.description}</span>
          </button>
        ))}
      </div>
    </section>
  );
};

export default SizePanel;
