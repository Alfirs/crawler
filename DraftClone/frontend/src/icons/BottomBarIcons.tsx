import type { FC, SVGProps } from 'react';

const BaseIcon: FC<SVGProps<SVGSVGElement>> = ({ children, ...props }) => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
    {children}
  </svg>
);

export const TemplateIcon = () => (
  <BaseIcon>
    <path d="M4 4h16v8H4z" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M4 16h7v4H4zM17 16h3v4h-3z" strokeLinecap="round" strokeLinejoin="round" />
  </BaseIcon>
);

export const BackgroundIcon = () => (
  <BaseIcon>
    <path d="M4 4h16v16H4z" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M4 10h16M10 4v16" strokeLinecap="round" />
  </BaseIcon>
);

export const TextIcon = () => (
  <BaseIcon>
    <path d="M6 6h12M6 10h12M6 14h8" strokeLinecap="round" />
  </BaseIcon>
);

export const LayoutIcon = () => (
  <BaseIcon>
    <rect x="4" y="4" width="16" height="16" rx="2" />
    <path d="M12 4v16" />
  </BaseIcon>
);

export const SizeIcon = () => (
  <BaseIcon>
    <path d="M8 4v12h12" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M12 4l-4 4M20 12l-4 4" strokeLinecap="round" strokeLinejoin="round" />
  </BaseIcon>
);

export const InfoIcon = () => (
  <BaseIcon>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v.01M11 11h1v5h1" strokeLinecap="round" strokeLinejoin="round" />
  </BaseIcon>
);

export const ExportIcon = () => (
  <BaseIcon>
    <path d="M12 4v12" strokeLinecap="round" />
    <path d="M8 8l4-4 4 4" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M4 16h16v4H4z" strokeLinecap="round" strokeLinejoin="round" />
  </BaseIcon>
);
