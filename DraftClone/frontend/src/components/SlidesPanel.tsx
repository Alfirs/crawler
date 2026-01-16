import { useEditorStore, usePost, useCurrentSlide } from '../state/useEditorStore';
import { useEffect, useRef, useState } from 'react';
import { THEMES } from '../constants/design';

const SlidesPanel = () => {
  const post = usePost();
  const currentSlide = useCurrentSlide();
  const setCurrentSlide = useEditorStore((state) => state.setCurrentSlide);
  const addSlide = useEditorStore((state) => state.addSlide);
  const moveSlide = useEditorStore((state) => state.moveSlide);
  const revision = useEditorStore((state) => state.revision);
  const [thumbs, setThumbs] = useState<Record<string, string>>({});
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const captureTimeout = useRef<number | null>(null);

  useEffect(() => {
    if (!currentSlide) return;
    if (captureTimeout.current) {
      window.clearTimeout(captureTimeout.current);
    }
    captureTimeout.current = window.setTimeout(async () => {
      const canvasRoot = document.querySelector('.preview-panel .canvas') as HTMLElement | null;
      if (!canvasRoot) return;
      try {
        const { default: html2canvas } = await import('html2canvas');
        const canvas = await html2canvas(canvasRoot, {
          backgroundColor: null,
          scale: 0.35,
          useCORS: true
        });
        setThumbs((prev) => ({
          ...prev,
          [currentSlide.id]: canvas.toDataURL('image/png')
        }));
      } catch (err) {
        console.warn('Thumbnail render failed', err);
      }
    }, 500);
    return () => {
      if (captureTimeout.current) {
        window.clearTimeout(captureTimeout.current);
      }
    };
  }, [revision, currentSlide?.id]);

  if (!post || !currentSlide) return null;

  return (
    <div className="slides-carousel">
      <div className="slides-strip">
        {post.slides.map((slide, idx) => {
          const isActive = slide.id === currentSlide.id;
          const className = ['strip-card', isActive && 'active', draggingId === slide.id && 'dragging']
            .filter(Boolean)
            .join(' ');
          const theme = THEMES[post.themeId] ?? THEMES.midnight;
          return (
            <button
              key={slide.id}
              type="button"
              className={className}
              onClick={() => setCurrentSlide(slide.id)}
              draggable
              onDragStart={(event) => {
                event.dataTransfer.effectAllowed = 'move';
                setDraggingId(slide.id);
              }}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                if (!draggingId || draggingId === slide.id) return;
                const fromIndex = post.slides.findIndex((s) => s.id === draggingId);
                moveSlide(draggingId, idx - fromIndex);
                setDraggingId(null);
              }}
              onDragEnd={() => setDraggingId(null)}
            >
              <div className="strip-thumb" style={{ background: theme.background }}>
                {thumbs[slide.id] ? (
                  <img src={thumbs[slide.id]} alt={slide.title || 'preview'} />
                ) : (
                  <div className="strip-fallback" style={{ color: theme.text }}>
                    <span>@{post.handle.replace('@', '')}</span>
                    <strong>{slide.title || 'Новый слайд'}</strong>
                  </div>
                )}
              </div>
              <div className="strip-meta">
                <small>@{post.handle.replace('@', '')}</small>
                <span>
                  {idx + 1}/{post.slides.length}
                </span>
              </div>
            </button>
          );
        })}
        <button type="button" className="strip-add" onClick={addSlide}>
          +
        </button>
      </div>
    </div>
  );
};

export default SlidesPanel;
