/** OpenNotebook — AppShell: top nav, sidebar, toast, command palette. */

import { useState, type ReactNode } from 'react';
import { BookOpen, Settings, LogOut, Search, Command } from 'lucide-react';
import { clsx } from 'clsx';
import { DarkModeToggle } from '@/components/ui/DarkModeToggle';
import { ToastContainer } from '@/components/ui/Toast';
import { CommandPalette } from '@/components/command/CommandPalette';
import { useCurrentUser, useLogout } from '@/hooks/useAuth';
import { useNotebooks } from '@/hooks/useNotebook';

interface AppShellProps {
  children: ReactNode;
  onNavigate: (path: string) => void;
  currentPath: string;
}

export function AppShell({ children, onNavigate, currentPath }: AppShellProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { data: user } = useCurrentUser();
  const logoutMutation = useLogout();
  const { data: notebooks = [] } = useNotebooks();

  return (
    <div className="flex h-screen overflow-hidden bg-surface-950">
      {/* Sidebar */}
      <aside
        className={clsx(
          'flex flex-col border-r border-surface-700/30 bg-surface-900/50 transition-all duration-300',
          sidebarCollapsed ? 'w-16' : 'w-60',
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 border-b border-surface-700/20 px-4 py-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-lg shadow-primary-500/20">
            <BookOpen className="h-4.5 w-4.5 text-white" />
          </div>
          {!sidebarCollapsed && (
            <div className="animate-fade-in">
              <p className="text-sm font-bold text-surface-100">OpenNotebook</p>
              <p className="text-[10px] text-surface-500">AI Research Assistant</p>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto p-2">
          <div className="mb-2">
            <NavItem
              icon={<BookOpen className="h-4 w-4" />}
              label="Notebooks"
              isActive={currentPath === '/notebooks'}
              collapsed={sidebarCollapsed}
              onClick={() => onNavigate('/notebooks')}
            />
          </div>

          {/* Notebook quick access */}
          {!sidebarCollapsed && notebooks.length > 0 && (
            <div className="mb-2">
              <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-surface-600">
                Recent
              </p>
              {notebooks.slice(0, 5).map((nb) => (
                <NavItem
                  key={nb.id}
                  icon={<span className="h-2 w-2 rounded-full bg-primary-500/60" />}
                  label={nb.name}
                  isActive={currentPath === `/notebooks/${nb.id}`}
                  collapsed={sidebarCollapsed}
                  onClick={() => onNavigate(`/notebooks/${nb.id}`)}
                />
              ))}
            </div>
          )}
        </nav>

        {/* Bottom */}
        <div className="border-t border-surface-700/20 p-2 space-y-1">
          <NavItem
            icon={<Settings className="h-4 w-4" />}
            label="Settings"
            isActive={currentPath === '/settings'}
            collapsed={sidebarCollapsed}
            onClick={() => onNavigate('/settings')}
          />

          {user && (
            <NavItem
              icon={<LogOut className="h-4 w-4" />}
              label="Sign out"
              collapsed={sidebarCollapsed}
              onClick={() => {
                logoutMutation.mutate(undefined, {
                  onSuccess: () => onNavigate('/'),
                });
              }}
            />
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center justify-between border-b border-surface-700/20 bg-surface-900/40 px-4 py-2">
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="rounded-lg p-1.5 text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-colors lg:hidden"
          >
            ☰
          </button>

          {/* Command palette trigger */}
          <button
            onClick={() => {
              const event = new KeyboardEvent('keydown', {
                key: 'k',
                metaKey: true,
              });
              document.dispatchEvent(event);
            }}
            className="flex items-center gap-2 rounded-xl border border-surface-700/30 bg-surface-800/40 px-3 py-1.5 text-xs text-surface-500 hover:text-surface-300 hover:border-surface-600 transition-colors"
          >
            <Search className="h-3.5 w-3.5" />
            <span>Search...</span>
            <kbd className="flex items-center gap-0.5 rounded border border-surface-700/40 bg-surface-800/60 px-1 py-0.5 text-[10px]">
              <Command className="h-2.5 w-2.5" />K
            </kbd>
          </button>

          <DarkModeToggle />
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-hidden">
          {children}
        </div>
      </main>

      {/* Command palette */}
      <CommandPalette onNavigate={onNavigate} />

      {/* Toast notifications */}
      <ToastContainer />
    </div>
  );
}

function NavItem({
  icon,
  label,
  isActive,
  collapsed,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  isActive?: boolean;
  collapsed: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-all',
        isActive
          ? 'bg-primary-600/15 text-primary-300 border border-primary-500/20'
          : 'text-surface-400 hover:bg-surface-800/60 hover:text-surface-200 border border-transparent',
        collapsed && 'justify-center px-0',
      )}
      title={collapsed ? label : undefined}
    >
      <span className="shrink-0">{icon}</span>
      {!collapsed && <span className="truncate">{label}</span>}
    </button>
  );
}
