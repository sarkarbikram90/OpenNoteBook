/** OpenNotebook — Notebook card for the dashboard grid. */

import { clsx } from 'clsx';
import { BookOpen, FileText, Clock } from 'lucide-react';
import type { Notebook } from '@/lib/types';

interface NotebookCardProps {
  notebook: Notebook;
  onClick: () => void;
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

const gradients = [
  'from-primary-600 to-violet-600',
  'from-emerald-600 to-teal-600',
  'from-amber-600 to-orange-600',
  'from-rose-600 to-pink-600',
  'from-blue-600 to-cyan-600',
  'from-fuchsia-600 to-purple-600',
];

export function NotebookCard({ notebook, onClick }: NotebookCardProps) {
  // Deterministic gradient based on name hash
  const gradientIdx =
    notebook.name.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % gradients.length;

  return (
    <button
      onClick={onClick}
      className={clsx(
        'group relative flex flex-col rounded-2xl border border-surface-700/30 bg-surface-800/40 p-5 text-left transition-all duration-200',
        'hover:border-surface-600/60 hover:bg-surface-800/70 hover:shadow-xl hover:shadow-black/20',
        'active:scale-[0.98]',
      )}
    >
      {/* Gradient accent bar */}
      <div
        className={clsx(
          'absolute top-0 left-4 right-4 h-1 rounded-b-full bg-gradient-to-r opacity-60 group-hover:opacity-100 transition-opacity',
          gradients[gradientIdx],
        )}
      />

      {/* Icon */}
      <div
        className={clsx(
          'flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br shadow-lg mb-4',
          gradients[gradientIdx],
        )}
      >
        <BookOpen className="h-5 w-5 text-white" />
      </div>

      {/* Content */}
      <h3 className="text-base font-semibold text-surface-100 group-hover:text-white transition-colors mb-1 line-clamp-1">
        {notebook.name}
      </h3>

      {notebook.description && (
        <p className="text-sm text-surface-400 line-clamp-2 mb-4">
          {notebook.description}
        </p>
      )}

      <div className="mt-auto flex items-center gap-4 text-xs text-surface-500">
        <span className="flex items-center gap-1">
          <FileText className="h-3.5 w-3.5" />
          {notebook.source_count} source{notebook.source_count !== 1 ? 's' : ''}
        </span>
        <span className="flex items-center gap-1">
          <Clock className="h-3.5 w-3.5" />
          {timeAgo(notebook.updated_at)}
        </span>
      </div>
    </button>
  );
}
