import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { getTheme, setTheme } from '../storage/storage';
import type { ThemeName } from './names';
import { THEMES, type Theme } from './themes';

type ThemeContextValue = { theme: Theme; name: ThemeName; setName: (name: ThemeName) => void };

const ThemeContext = createContext<ThemeContextValue>({
  theme: THEMES.dark,
  name: 'dark',
  setName: () => undefined,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [name, setNameState] = useState<ThemeName>('dark');

  useEffect(() => {
    let active = true;
    getTheme()
      .then((saved) => {
        if (active) setNameState(saved);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const setName = useCallback((next: ThemeName) => {
    setNameState(next);
    setTheme(next).catch(() => undefined);
  }, []);

  const value = useMemo(() => ({ theme: THEMES[name], name, setName }), [name, setName]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
