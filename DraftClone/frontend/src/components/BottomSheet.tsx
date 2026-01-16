import type { ReactNode } from 'react';

type BottomSheetProps = {
  open: boolean;
  title: string;
  children: ReactNode;
  applyAllValue: boolean;
  onToggleApply: (value: boolean) => void;
  onClose: () => void;
  onApply?: () => void;
};

const BottomSheet = ({
  open,
  title,
  children,
  applyAllValue,
  onToggleApply,
  onClose,
  onApply
}: BottomSheetProps) => {
  const handleApply = () => {
    onApply?.();
    onClose();
  };

  if (!open) return null;

  return (
    <>
      <div className="sheet-overlay" onClick={onClose} />
      <div className="bottom-sheet">
        <div className="sheet-handle" />
        <header className="sheet-header">
          <h3>{title}</h3>
        </header>
        <div className="sheet-body">{children}</div>
        <div className="sheet-footer">
          <label className="apply-toggle">
            <input
              type="checkbox"
              checked={applyAllValue}
              onChange={(event) => onToggleApply(event.target.checked)}
            />
            <span>Применить ко всем слайдам</span>
          </label>
          <div className="sheet-actions">
            <button type="button" className="ghost" onClick={onClose}>
              Отменить
            </button>
            <button type="button" className="primary" onClick={handleApply}>
              Сохранить
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

export default BottomSheet;
