/** OpenNotebook — Chat session sidebar with session list and management. */

import { clsx } from 'clsx';
import { Plus, MessageSquare, Trash2, Download } from 'lucide-react';
import type { ChatSession } from '@/lib/types';

interface SessionSidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  onExportSession: (sessionId: string) => void;
  isLoading?: boolean;
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onExportSession,
  isLoading,
}: SessionSidebarProps) {
  return (
    <div className="flex h-full flex-col border-r border-surface-700/40 bg-surface-900/50 w-64">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-surface-700/30 px-4 py-3">
        <h3 className="text-sm font-semibold text-surface-200">Chats</h3>
        <button
          onClick={onNewSession}
          className="rounded-lg p-1.5 text-surface-400 transition-colors hover:bg-surface-800 hover:text-primary-400"
          title="New chat"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto p-2">
        {isLoading ? (
          <div className="space-y-2 p-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 rounded-lg bg-surface-800/60 animate-shimmer" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <MessageSquare className="h-10 w-10 text-surface-600 mb-3" />
            <p className="text-sm text-surface-500">No chats yet</p>
            <p className="text-xs text-surface-600 mt-1">Start a conversation!</p>
          </div>
        ) : (
          <div className="space-y-1">
            {sessions.map((session) => (
              <div
                key={session.id}
                className={clsx(
                  'group flex items-center gap-2 rounded-lg px-3 py-2.5 cursor-pointer transition-all',
                  activeSessionId === session.id
                    ? 'bg-primary-600/15 border border-primary-500/20 text-surface-100'
                    : 'text-surface-400 hover:bg-surface-800/60 hover:text-surface-200 border border-transparent',
                )}
                onClick={() => onSelectSession(session.id)}
              >
                <MessageSquare className="h-4 w-4 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate">{session.title}</p>
                  <p className="text-xs text-surface-500 mt-0.5">
                    {session.message_count} messages
                  </p>
                </div>

                {/* Actions */}
                <div className="flex shrink-0 gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onExportSession(session.id);
                    }}
                    className="rounded p-1 text-surface-500 hover:text-surface-300 hover:bg-surface-700/50"
                    title="Export"
                  >
                    <Download className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession(session.id);
                    }}
                    className="rounded p-1 text-surface-500 hover:text-red-400 hover:bg-red-500/10"
                    title="Delete"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
