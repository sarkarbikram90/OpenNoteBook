/**
 * OpenNotebook — useDarkMode hook.
 *
 * Reads prefers-color-scheme, persists preference to localStorage,
 * and toggles the dark/light class on <html>.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  getStoredTheme,
  setStoredTheme,
  applyTheme,
  type ThemeMode,
} from '@/stores/theme';

interface UseDarkModeReturn {
  mode: ThemeMode;
  isDark: boolean;
  setMode: (mode: ThemeMode) => void;
  toggle: () => void;
}

export function useDarkMode(): UseDarkModeReturn {
  const [mode, setModeState] = useState<ThemeMode>(() => getStoredTheme());

  // Apply theme on mount and mode change
  useEffect(() => {
    applyTheme(mode);
  }, [mode]);

  // Listen for system preference changes when in 'system' mode
  useEffect(() => {
    if (mode !== 'system') return;

    const mql = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => applyTheme('system');

    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, [mode]);

  const setMode = useCallback((newMode: ThemeMode) => {
    setModeState(newMode);
    setStoredTheme(newMode);
    applyTheme(newMode);
  }, []);

  const toggle = useCallback(() => {
    setMode(mode === 'dark' ? 'light' : 'dark');
  }, [mode, setMode]);

  const isDark =
    mode === 'dark' ||
    (mode === 'system' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches);

  return { mode, isDark, setMode, toggle };
}
