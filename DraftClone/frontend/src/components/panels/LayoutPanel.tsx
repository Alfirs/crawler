import { useCurrentSlide, useEditorStore } from '../../state/useEditorStore';

const layouts = [
  { id: 'stacked', label: 'Stacked', description: 'Вертикальное расположение' },
  { id: 'split', label: 'Split', description: 'Текст + визуал' },
  { id: 'centered', label: 'Centered', description: 'Выровнено по центру' }
];

const LayoutPanel = () => {
  const slide = useCurrentSlide();
  const updateSlideField = useEditorStore((state) => state.updateSlideField);
  if (!slide) return null;

  return (
    <section className="tab-panel">
      <p className="muted">Ориентация сетки текущего слайда.</p>
      <div className="chip-group">
        {layouts.map((layout) => (
          <button
            key={layout.id}
            className={layout.id === slide.layout ? 'chip active' : 'chip'}
            type="button"
            onClick={() => updateSlideField(slide.id, 'layout', layout.id)}
          >
            <strong>{layout.label}</strong>
            <span>{layout.description}</span>
          </button>
        ))}
      </div>
    </section>
  );
};

export default LayoutPanel;
