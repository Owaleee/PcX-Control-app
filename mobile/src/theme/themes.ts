import type { ThemeName } from './names';

export type Theme = {
  name: ThemeName;
  background: string;
  surface: string;
  text: string;
  textMuted: string;
  accent: string;
  danger: string;
  track: string;
  border: string;
  statusBar: 'light' | 'dark';
};

export const THEMES: Record<ThemeName, Theme> = {
  dark: {
    name: 'dark',
    background: '#0F172A',
    surface: '#1E293B',
    text: '#F8FAFC',
    textMuted: '#CBD5E1',
    accent: '#38BDF8',
    danger: '#FDA4AF',
    track: '#475569',
    border: '#334155',
    statusBar: 'light',
  },
  light: {
    name: 'light',
    background: '#F1F5F9',
    surface: '#FFFFFF',
    text: '#0F172A',
    textMuted: '#475569',
    accent: '#0369A1',
    danger: '#BE123C',
    track: '#CBD5E1',
    border: '#E2E8F0',
    statusBar: 'dark',
  },
  amoled: {
    name: 'amoled',
    background: '#000000',
    surface: '#0A0A0A',
    text: '#F5F5F5',
    textMuted: '#A3A3A3',
    accent: '#22D3EE',
    danger: '#FB7185',
    track: '#262626',
    border: '#1F1F1F',
    statusBar: 'light',
  },
};

const ORDER: readonly ThemeName[] = ['dark', 'light', 'amoled'];

export function nextTheme(name: ThemeName): ThemeName {
  return ORDER[(ORDER.indexOf(name) + 1) % ORDER.length] ?? 'dark';
}

function luminance(hex: string): number {
  const value = hex.replace('#', '');
  const channels = [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
}

/** Contraste WCAG entre duas cores #RRGGBB (1 a 21). */
export function contrastRatio(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (light + 0.05) / (dark + 0.05);
}
