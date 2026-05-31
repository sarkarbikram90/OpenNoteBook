import { describe, it, expect, beforeEach, vi } from 'vitest';
import { getStoredTheme, setStoredTheme, resolveTheme, applyTheme } from './theme';

describe('theme store', () => {
  beforeEach(() => {
    localStorage.clear();
    // Reset document element classlist
    document.documentElement.className = '';
    vi.restoreAllMocks();
  });

  it('should default to dark theme when nothing is stored', () => {
    expect(getStoredTheme()).toBe('dark');
  });

  it('should store and retrieve theme mode', () => {
    setStoredTheme('light');
    expect(getStoredTheme()).toBe('light');
    
    setStoredTheme('system');
    expect(getStoredTheme()).toBe('system');
  });

  it('should resolve explicit themes', () => {
    expect(resolveTheme('light')).toBe('light');
    expect(resolveTheme('dark')).toBe('dark');
  });

  it('should resolve system theme based on prefers-color-scheme', () => {
    // Mock window.matchMedia
    const matchMediaMock = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('dark'),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    vi.stubGlobal('window', { matchMedia: matchMediaMock });

    expect(resolveTheme('system')).toBe('dark');
  });

  it('should apply theme class to documentElement', () => {
    applyTheme('light');
    expect(document.documentElement.classList.contains('light')).toBe(true);
    expect(document.documentElement.classList.contains('dark')).toBe(false);

    applyTheme('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.classList.contains('light')).toBe(false);
  });
});
