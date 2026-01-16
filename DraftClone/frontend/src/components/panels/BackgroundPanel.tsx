import { useEffect, useMemo, useState } from 'react';
import { uploadBackgroundImage } from '../../api/posts';
import { THEMES } from '../../constants/design';
import { useEditorStore, usePost } from '../../state/useEditorStore';

const GRADIENT_PRESETS = [
  { id: 'dawn', name: 'Dawn', from: '#0f0c29', to: '#302b63', angle: 135 },
  { id: 'citrus', name: 'Citrus', from: '#ff9966', to: '#ff5e62', angle: 120 },
  { id: 'aqua', name: 'Aqua', from: '#0099f7', to: '#f11712', angle: 140 },
  { id: 'forest', name: 'Forest', from: '#134e5e', to: '#71b280', angle: 160 }
];

const BackgroundPanel = () => {
  const post = usePost();
  const setTheme = useEditorStore((state) => state.setTheme);
  const setPalette = useEditorStore((state) => state.setPalette);
  const setBackground = useEditorStore((state) => state.setBackground);
  const savePreset = useEditorStore((state) => state.saveBrandPreset);
  const applyPreset = useEditorStore((state) => state.applyBrandPreset);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customPalette, setCustomPalette] = useState(
    post?.settings?.palette || { background: '#0f1117', text: '#f4f4f4', accent: '#9db5ff' }
  );

  useEffect(() => {
    if (post?.settings?.palette) {
      setCustomPalette(post.settings.palette);
    }
  }, [post?.settings?.palette]);

  if (!post) return null;

  const gradients = useMemo(() => {
    const library = post.settings?.backgroundLibrary?.gradients || [];
    const presetMap = new Map<string, { id: string; name: string; from: string; to: string; angle?: number }>();
    [...GRADIENT_PRESETS, ...library].forEach((gradient) => {
      presetMap.set(gradient.id, gradient);
    });
    return Array.from(presetMap.values());
  }, [post.settings?.backgroundLibrary?.gradients]);

  const images = post.settings?.backgroundLibrary?.images || [];
  const brandKit = post.settings?.brandKit;

  const handlePaletteChange = (field: 'background' | 'text' | 'accent') => (event: any) => {
    setCustomPalette((prev) => ({ ...prev, [field]: event.target.value }));
  };

  const applyCustomPalette = () => {
    setPalette(customPalette);
  };

  const handleGradientSelect = (gradient: { from: string; to: string; angle?: number }) => {
    setBackground({
      type: 'gradient',
      value: gradient.from,
      gradient
    });
  };

  const handleImageUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!post) return;
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const url = await uploadBackgroundImage(post, file);
      setBackground({
        type: 'image',
        imageUrl: url
      });
    } catch (err) {
      console.error(err);
      setError('Не удалось загрузить изображение');
    } finally {
      setUploading(false);
    }
  };

  const saveBrand = () => {
    const name = window.prompt('Название набора', 'Custom brand');
    if (!name) return;
    savePreset(name);
  };

  return (
    <div className="background-sheet">
      <section>
        <h4>Темы</h4>
        <div className="theme-grid">
          {Object.entries(THEMES).map(([id, palette]) => (
            <button
              key={id}
              className={id === post.themeId ? 'theme-card active' : 'theme-card'}
              type="button"
              onClick={() => setTheme(id)}
            >
              <div className="theme-preview" style={{ background: palette.background }}>
                <span style={{ color: palette.text }}>Aa</span>
                <span style={{ color: palette.accent }}>Bb</span>
              </div>
              <strong>{palette.label}</strong>
              <span>{palette.background}</span>
            </button>
          ))}
        </div>
      </section>

      {brandKit && (
        <section>
          <div className="brand-header">
            <h4>Brand kits</h4>
            <button type="button" onClick={saveBrand}>
              + Сохранить набор
            </button>
          </div>
          <div className="brand-grid">
            {brandKit.presets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                className={preset.id === brandKit.activeId ? 'brand-card active' : 'brand-card'}
                onClick={() => applyPreset(preset.id)}
              >
                <span
                  className="theme-preview"
                  style={{ background: preset.palette.background, color: preset.palette.accent }}
                >
                  ●
                </span>
                <strong>{preset.name}</strong>
                <span>
                  {preset.palette.background} / {preset.palette.accent}
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="palette-editor">
        <h4>Своя палитра</h4>
        <div className="palette-fields">
          <label>
            Background
            <input type="color" value={customPalette.background} onChange={handlePaletteChange('background')} />
          </label>
          <label>
            Text
            <input type="color" value={customPalette.text} onChange={handlePaletteChange('text')} />
          </label>
          <label>
            Accent
            <input type="color" value={customPalette.accent} onChange={handlePaletteChange('accent')} />
          </label>
        </div>
        <button type="button" onClick={applyCustomPalette}>
          Применить палитру
        </button>
      </section>

      <section>
        <h4>Градиенты</h4>
        <div className="gradient-grid">
          {gradients.map((gradient) => (
            <button
              key={gradient.id}
              type="button"
              className="gradient-card"
              style={{
                background: `linear-gradient(${gradient.angle ?? 135}deg, ${gradient.from}, ${gradient.to})`
              }}
              onClick={() => handleGradientSelect(gradient)}
            >
              <strong>{gradient.name}</strong>
              <span>
                {gradient.from} → {gradient.to}
              </span>
            </button>
          ))}
        </div>
      </section>

      <section>
        <h4>Фоны с изображениями</h4>
        <label className="upload-tile">
          <input type="file" accept="image/png,image/jpeg,image/webp" disabled={uploading} onChange={handleImageUpload} />
          {uploading ? 'Загружается…' : '+ Добавить изображение'}
        </label>
        {error && <p className="error-text">{error}</p>}
        <div className="image-grid">
          {images.map((url) => (
            <button
              type="button"
              key={url}
              className="image-thumb"
              onClick={() =>
                setBackground({
                  type: 'image',
                  imageUrl: url
                })
              }
            >
              <img src={url} alt="Background" />
            </button>
          ))}
          {images.length === 0 && <p className="muted">Фонов пока нет — загрузите первое изображение.</p>}
        </div>
      </section>
    </div>
  );
};

export default BackgroundPanel;
