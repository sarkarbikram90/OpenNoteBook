/** OpenNotebook — Notebook workspace: split layout with sources sidebar and main panel. */

import { useState } from 'react';
import { MessageSquare, FolderOpen, ChevronLeft } from 'lucide-react';
import { clsx } from 'clsx';
import { useNotebook } from '@/hooks/useNotebook';
import { ChatWorkspace } from '@/components/chat/ChatWorkspace';
import { SourceLibrary } from '@/components/source/SourceLibrary';
import { Spinner } from '@/components/ui/Spinner';

interface NotebookWorkspaceProps {
  notebookId: string;
  onBack: () => void;
}

type Tab = 'chat' | 'sources';

export function NotebookWorkspace({ notebookId, onBack }: NotebookWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<Tab>('chat');
  const { data: notebook, isLoading } = useNotebook(notebookId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!notebook) {
    return (
      <div className="flex items-center justify-center h-full text-surface-400">
        Notebook not found
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b border-surface-700/30 bg-surface-900/60 px-4 py-2.5">
        <button
          onClick={onBack}
          className="rounded-lg p-1.5 text-surface-400 hover:text-surface-200 hover:bg-surface-800 transition-colors"
          title="Back to notebooks"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>

        <h1 className="text-sm font-semibold text-surface-200 truncate">
          {notebook.name}
        </h1>

        {/* Tab switcher */}
        <div className="ml-auto flex items-center gap-1 rounded-xl bg-surface-800/60 p-1 border border-surface-700/30">
          {([
            ['chat', MessageSquare, 'Chat'],
            ['sources', FolderOpen, 'Sources'],
          ] as const).map(([key, Icon, label]) => (
            <button
              key={key}
              onClick={() => setActiveTab(key as Tab)}
              className={clsx(
                'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all',
                activeTab === key
                  ? 'bg-primary-600 text-white shadow-md'
                  : 'text-surface-400 hover:text-surface-200',
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Main panel */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'chat' ? (
          <ChatWorkspace notebookId={notebookId} />
        ) : (
          <SourceLibrary notebookId={notebookId} />
        )}
      </div>
    </div>
  );
}
