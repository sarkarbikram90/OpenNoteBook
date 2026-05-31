/**
 * OpenNotebook — Theme store.
 *
 * Manages dark/light/system theme preference with localStorage persistence.
 */

export type ThemeMode = 'light' | 'dark' | 'system';

const THEME_KEY = 'opennotebook_theme';

/** Get stored theme preference. Defaults to 'dark'. */
export function getStoredTheme(): ThemeMode {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === 'light' || stored === 'dark' || stored === 'system') {
    return stored;
  }
  return 'dark';
}

/** Persist theme preference. */
export function setStoredTheme(mode: ThemeMode): void {
  localStorage.setItem(THEME_KEY, mode);
}

/** Resolve effective theme considering system preference. */
export function resolveTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
  }
  return mode;
}

/** Apply theme to the HTML element. */
export function applyTheme(mode: ThemeMode): void {
  const resolved = resolveTheme(mode);
  const html = document.documentElement;
  html.classList.remove('light', 'dark');
  html.classList.add(resolved);
}
