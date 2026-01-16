import type { ReactNode } from 'react';

type TabItem = {
  id: string;
  label: string;
  icon?: ReactNode;
  badge?: string;
  badgeTitle?: string;
};

type TabsProps = {
  items: TabItem[];
  active: string;
  onChange: (value: string) => void;
};

const Tabs = ({ items, active, onChange }: TabsProps) => (
  <nav className="editor-tabs">
    {items.map((item) => (
      <button
        key={item.id}
        type="button"
        className={item.id === active ? 'tab active' : 'tab'}
        onClick={() => onChange(item.id)}
        title={item.badgeTitle}
      >
        {item.icon && <span className="tab-icon">{item.icon}</span>}
        <span>{item.label}</span>
        {item.badge && <span className="tab-badge">{item.badge}</span>}
      </button>
    ))}
  </nav>
);

export default Tabs;
