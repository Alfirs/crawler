import { useState } from 'react';

type ExportPanelProps = {
  onExport: (options: { format: 'png' | 'pdf'; range: 'all' | 'current' }) => Promise<void>;
};

const ExportPanel = ({ onExport }: ExportPanelProps) => {
  const [format, setFormat] = useState<'png' | 'pdf'>('png');
  const [range, setRange] = useState<'all' | 'current'>('all');
  const [isProcessing, setProcessing] = useState(false);

  const handleExport = async () => {
    setProcessing(true);
    try {
      await onExport({ format, range });
    } finally {
      setProcessing(false);
    }
  };

  return (
    <section className="tab-panel">
      <p className="muted">Скоро появится полноценный экспорт. Пока можно запросить заглушку.</p>
      <div className="export-options">
        <label>
          Формат
          <select value={format} onChange={(e) => setFormat(e.target.value as 'png' | 'pdf')}>
            <option value="png">PNG</option>
            <option value="pdf">PDF</option>
          </select>
        </label>
        <label>
          Диапазон
          <select value={range} onChange={(e) => setRange(e.target.value as 'all' | 'current')}>
            <option value="all">Все слайды</option>
            <option value="current">Текущий</option>
          </select>
        </label>
        <button type="button" onClick={handleExport} disabled={isProcessing}>
          {isProcessing ? 'Готовим…' : 'Экспортировать'}
        </button>
      </div>
    </section>
  );
};

export default ExportPanel;
