type Action = {
  id: string;
  label: string;
};

const ACTIONS: Action[] = [
  { id: 'improve', label: 'Improve' },
  { id: 'shorten', label: 'Shorten' },
  { id: 'expand', label: 'Expand' },
  { id: 'simplify', label: 'Simplify' },
  { id: 'tone_friendly', label: 'Friendly tone' },
  { id: 'tone_professional', label: 'Pro tone' },
  { id: 'translate_ru', label: 'Translate → RU' },
  { id: 'translate_en', label: 'Translate → EN' }
];

type AIActionBarProps = {
  onAction: (actionId: string) => void;
  isRunning?: boolean;
  lastAction?: string | null;
};

const AIActionBar = ({ onAction, isRunning, lastAction }: AIActionBarProps) => (
  <div className="ai-actions">
    <span className="muted">AI assist</span>
    {ACTIONS.map((action) => (
      <button key={action.id} type="button" disabled={isRunning} onClick={() => onAction(action.id)}>
        {action.label}
        {lastAction === action.id && <span className="ai-badge">✓</span>}
      </button>
    ))}
    </div>
);

export default AIActionBar;
