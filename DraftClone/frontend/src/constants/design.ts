export const THEMES: Record<
  string,
  {
    label: string;
    background: string;
    text: string;
    accent: string;
  }
> = {
  midnight: {
    label: 'Midnight',
    background: '#0f1117',
    text: '#f4f4f4',
    accent: '#9db5ff'
  },
  sunrise: {
    label: 'Sunrise',
    background: '#fff8ef',
    text: '#2c2c2c',
    accent: '#ff6f3c'
  },
  forest: {
    label: 'Forest',
    background: '#0f1f1a',
    text: '#f0f7f2',
    accent: '#4fe3a5'
  },
  violet: {
    label: 'Violet',
    background: '#1a1325',
    text: '#f6edff',
    accent: '#bb98ff'
  }
};

export const TYPOGRAPHY: Record<
  string,
  {
    label: string;
    headline: string;
    body: string;
  }
> = {
  'montserrat-pt': {
    label: 'Montserrat / PT Sans',
    headline: '"Montserrat", sans-serif',
    body: '"PT Sans", sans-serif'
  },
  'inter-inter': {
    label: 'Inter / Inter',
    headline: '"Inter", sans-serif',
    body: '"Inter", sans-serif'
  },
  'playfair-source': {
    label: 'Playfair / Source Sans',
    headline: '"Playfair Display", serif',
    body: '"Source Sans Pro", sans-serif'
  }
};
