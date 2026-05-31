/** OpenNotebook — Dark mode toggle with sun/moon animation. */

import { Sun, Moon, Monitor } from 'lucide-react';
import { clsx } from 'clsx';
import { useDarkMode } from '@/hooks/useDarkMode';
import type { ThemeMode } from '@/stores/theme';

export function DarkModeToggle() {
  const { mode, setMode } = useDarkMode();

  const modes: { value: ThemeMode; icon: typeof Sun; label: string }[] = [
    { value: 'light', icon: Sun, label: 'Light' },
    { value: 'dark', icon: Moon, label: 'Dark' },
    { value: 'system', icon: Monitor, label: 'System' },
  ];

  return (
    <div className="flex items-center gap-0.5 rounded-xl bg-surface-800/60 p-1 border border-surface-700/30">
      {modes.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          onClick={() => setMode(value)}
          className={clsx(
            'rounded-lg p-1.5 transition-all duration-200',
            mode === value
              ? 'bg-primary-600 text-white shadow-md shadow-primary-500/20'
              : 'text-surface-400 hover:text-surface-200 hover:bg-surface-700/50',
          )}
          title={label}
          aria-label={`Switch to ${label} mode`}
        >
          <Icon className="h-4 w-4" />
        </button>
      ))}
    </div>
  );
}
