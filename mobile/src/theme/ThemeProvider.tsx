// Preferencias de exibicao: tema e numeros precisos.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { formatPercent } from '../format/format';
import { getPrecise, getTheme, setPrecise as savePrecise, setTheme } from '../storage/storage';
import type { ThemeName } from './names';
import { THEMES, type Theme } from './themes';

type ThemeContextValue = {
  theme: Theme;
  name: ThemeName;
  setName: (name: ThemeName) => void;
  precise: boolean;
  setPrecise: (precise: boolean) => void;
};

const ThemeContext = createContext<ThemeContextValue>({
  theme: THEMES.dark,
  name: 'dark',
  setName: () => undefined,
  precise: false,
  setPrecise: () => undefined,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [name, setNameState] = useState<ThemeName>('dark');
  const [precise, setPreciseState] = useState(false);

  useEffect(() => {
    let active = true;
    getTheme()
      .then((saved) => active && setNameState(saved))
      .catch(() => undefined);
    getPrecise()
      .then((saved) => active && setPreciseState(saved))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const setName = useCallback((next: ThemeName) => {
    setNameState(next);
    setTheme(next).catch(() => undefined);
  }, []);

  const setPrecise = useCallback((next: boolean) => {
    setPreciseState(next);
    savePrecise(next).catch(() => undefined);
  }, []);

  const value = useMemo(
    () => ({ theme: THEMES[name], name, setName, precise, setPrecise }),
    [name, setName, precise, setPrecise],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}

/** Formata percentuais seguindo a opcao "Numeros precisos". */
export function usePercent(): (value: number) => string {
  const { precise } = useTheme();
  return useCallback((value: number) => formatPercent(value, { precise }), [precise]);
}
