/** OpenNotebook — Command palette (⌘K) powered by cmdk. */

import { useState, useEffect } from 'react';
import { Command } from 'cmdk';
import {
  BookOpen, Plus, Search, Settings, Moon, Sun,
} from 'lucide-react';
import { useNotebooks } from '@/hooks/useNotebook';
import { useDarkMode } from '@/hooks/useDarkMode';

interface CommandPaletteProps {
  onNavigate: (path: string) => void;
}

export function CommandPalette({ onNavigate }: CommandPaletteProps) {
  const [open, setOpen] = useState(false);
  const { data: notebooks = [] } = useNotebooks();
  const { isDark, toggle } = useDarkMode();

  // Listen for ⌘K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      // Keyboard shortcuts (when palette is closed)
      if (!open && e.target === document.body) {
        if (e.key === 'n' && !e.metaKey && !e.ctrlKey) {
          // 'N' for new notebook — handled by dashboard
        }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setOpen(false)}
      />

      {/* Command dialog */}
      <div className="flex items-start justify-center pt-[20vh] px-4">
        <Command
          className="w-full max-w-lg rounded-2xl border border-surface-700/50 bg-surface-900 shadow-2xl shadow-black/40 overflow-hidden animate-scale-in"
          loop
        >
          <div className="flex items-center gap-3 border-b border-surface-700/30 px-4">
            <Search className="h-4 w-4 text-surface-500 shrink-0" />
            <Command.Input
              placeholder="Search notebooks, actions..."
              className="flex-1 bg-transparent py-3.5 text-sm text-surface-100 placeholder:text-surface-500 outline-none"
              autoFocus
            />
            <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded-md border border-surface-700/40 bg-surface-800/60 px-1.5 py-0.5 text-[10px] text-surface-500">
              ESC
            </kbd>
          </div>

          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="py-8 text-center text-sm text-surface-500">
              No results found.
            </Command.Empty>

            {/* Quick Actions */}
            <Command.Group heading="Actions" className="mb-2">
              <CommandItem
                onSelect={() => { onNavigate('/notebooks'); setOpen(false); }}
                icon={<BookOpen className="h-4 w-4" />}
                label="All Notebooks"
                shortcut="⌘1"
              />
              <CommandItem
                onSelect={() => { onNavigate('/notebooks?create=true'); setOpen(false); }}
                icon={<Plus className="h-4 w-4" />}
                label="New Notebook"
                shortcut="N"
              />
              <CommandItem
                onSelect={() => { onNavigate('/settings'); setOpen(false); }}
                icon={<Settings className="h-4 w-4" />}
                label="Settings"
              />
              <CommandItem
                onSelect={() => { toggle(); setOpen(false); }}
                icon={isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                label={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
              />
            </Command.Group>

            {/* Notebooks */}
            {notebooks.length > 0 && (
              <Command.Group heading="Notebooks" className="mb-2">
                {notebooks.map((nb) => (
                  <CommandItem
                    key={nb.id}
                    onSelect={() => { onNavigate(`/notebooks/${nb.id}`); setOpen(false); }}
                    icon={<BookOpen className="h-4 w-4" />}
                    label={nb.name}
                    subtitle={`${nb.source_count} sources`}
                  />
                ))}
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}

function CommandItem({
  onSelect,
  icon,
  label,
  subtitle,
  shortcut,
}: {
  onSelect: () => void;
  icon: React.ReactNode;
  label: string;
  subtitle?: string;
  shortcut?: string;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-surface-300 cursor-pointer transition-colors data-[selected=true]:bg-primary-600/15 data-[selected=true]:text-surface-100"
    >
      <span className="text-surface-500">{icon}</span>
      <span className="flex-1">{label}</span>
      {subtitle && <span className="text-xs text-surface-500">{subtitle}</span>}
      {shortcut && (
        <kbd className="rounded border border-surface-700/30 bg-surface-800/40 px-1.5 py-0.5 text-[10px] text-surface-500">
          {shortcut}
        </kbd>
      )}
    </Command.Item>
  );
}
