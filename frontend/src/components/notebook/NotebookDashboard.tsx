/** OpenNotebook — Notebook dashboard with grid, search, and create. */

import { useState } from 'react';
import { Plus, Search, BookOpen } from 'lucide-react';
import { useNotebooks, useCreateNotebook } from '@/hooks/useNotebook';
import { NotebookCard } from '@/components/notebook/NotebookCard';
import { CreateNotebookModal } from '@/components/notebook/CreateNotebookModal';
import { Spinner } from '@/components/ui/Spinner';

interface NotebookDashboardProps {
  onSelectNotebook: (id: string) => void;
}

export function NotebookDashboard({ onSelectNotebook }: NotebookDashboardProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState('');

  const { data: notebooks = [], isLoading } = useNotebooks();
  const createMutation = useCreateNotebook();

  const filtered = notebooks.filter(
    (nb) =>
      nb.name.toLowerCase().includes(search.toLowerCase()) ||
      nb.description?.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Header */}
      <div className="border-b border-surface-700/30 bg-surface-900/60 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-surface-100">Notebooks</h1>
              <p className="text-sm text-surface-500 mt-0.5">
                {notebooks.length} notebook{notebooks.length !== 1 ? 's' : ''}
              </p>
            </div>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-primary-500 shadow-lg shadow-primary-500/20 active:scale-95"
            >
              <Plus className="h-4 w-4" />
              New Notebook
            </button>
          </div>

          {/* Search */}
          {notebooks.length > 0 && (
            <div className="relative max-w-md">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-surface-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search notebooks..."
                className="w-full rounded-xl border border-surface-700/30 bg-surface-800/40 pl-10 pr-4 py-2.5 text-sm text-surface-200 placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
              />
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-6 py-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Spinner size="lg" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-xl shadow-primary-500/20 mb-6">
              <BookOpen className="h-10 w-10 text-white" />
            </div>
            <h2 className="text-xl font-semibold text-surface-200 mb-2">
              {notebooks.length === 0
                ? 'Create your first notebook'
                : 'No matching notebooks'}
            </h2>
            <p className="text-sm text-surface-500 max-w-md mb-6">
              {notebooks.length === 0
                ? 'Notebooks are collections of sources and conversations. Upload documents, ask questions, and get grounded answers.'
                : 'Try adjusting your search query.'}
            </p>
            {notebooks.length === 0 && (
              <button
                onClick={() => setShowCreate(true)}
                className="flex items-center gap-2 rounded-xl bg-primary-600 px-5 py-2.5 text-sm font-medium text-white transition-all hover:bg-primary-500"
              >
                <Plus className="h-4 w-4" />
                Create Notebook
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((notebook) => (
              <NotebookCard
                key={notebook.id}
                notebook={notebook}
                onClick={() => onSelectNotebook(notebook.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create modal */}
      <CreateNotebookModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={(data) => {
          createMutation.mutate(data, {
            onSuccess: (nb) => {
              setShowCreate(false);
              onSelectNotebook(nb.id);
            },
          });
        }}
        isLoading={createMutation.isPending}
      />
    </div>
  );
}
