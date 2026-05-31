/** OpenNotebook — Source card with status badge and processing progress. */

import { clsx } from 'clsx';
import {
  FileText, Globe, Youtube, FileType, MoreVertical,
  Trash2, RefreshCw, Sparkles, ChevronRight,
} from 'lucide-react';
import { useState } from 'react';
import { Badge, statusBadgeVariant } from '@/components/ui/Badge';
import { ProcessingProgress } from '@/components/source/ProcessingProgress';
import type { Source } from '@/lib/types';

interface SourceCardProps {
  source: Source;
  onDelete: (id: string) => void;
  onReindex: (id: string) => void;
  onSummarize: (id: string) => void;
  onSelect: (id: string) => void;
}

const typeIcons: Record<string, typeof FileText> = {
  pdf: FileText,
  docx: FileType,
  txt: FileText,
  md: FileText,
  url: Globe,
  youtube: Youtube,
};

const typeColors: Record<string, string> = {
  pdf: 'text-red-400',
  docx: 'text-blue-400',
  txt: 'text-surface-400',
  md: 'text-emerald-400',
  url: 'text-amber-400',
  youtube: 'text-red-400',
};

export function SourceCard({
  source,
  onDelete,
  onReindex,
  onSummarize,
  onSelect,
}: SourceCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const Icon = typeIcons[source.source_type] || FileText;
  const isProcessing = !['READY', 'FAILED'].includes(source.status);

  return (
    <div
      className={clsx(
        'group relative rounded-xl border bg-surface-800/40 p-4 transition-all',
        'hover:bg-surface-800/70 hover:border-surface-600/50',
        isProcessing
          ? 'border-primary-500/20'
          : source.status === 'FAILED'
            ? 'border-red-500/20'
            : 'border-surface-700/30',
      )}
    >
      <div className="flex items-start gap-3">
        {/* Type icon */}
        <div
          className={clsx(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border',
            isProcessing
              ? 'bg-primary-500/10 border-primary-500/20'
              : 'bg-surface-700/40 border-surface-600/30',
          )}
        >
          <Icon className={clsx('h-5 w-5', typeColors[source.source_type] || 'text-surface-400')} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <button
              onClick={() => onSelect(source.id)}
              className="text-sm font-medium text-surface-200 hover:text-primary-400 transition-colors truncate text-left"
            >
              {source.name}
            </button>

            {/* Actions menu */}
            <div className="relative shrink-0">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="rounded-lg p-1 text-surface-500 opacity-0 group-hover:opacity-100 transition-all hover:bg-surface-700/50 hover:text-surface-300"
              >
                <MoreVertical className="h-4 w-4" />
              </button>

              {showMenu && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
                  <div className="absolute right-0 top-8 z-50 w-44 rounded-xl border border-surface-700/50 bg-surface-800 py-1 shadow-xl animate-scale-in">
                    <button
                      onClick={() => { onSummarize(source.id); setShowMenu(false); }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-surface-300 hover:bg-surface-700/50"
                    >
                      <Sparkles className="h-4 w-4" /> Generate summary
                    </button>
                    <button
                      onClick={() => { onReindex(source.id); setShowMenu(false); }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-surface-300 hover:bg-surface-700/50"
                    >
                      <RefreshCw className="h-4 w-4" /> Re-index
                    </button>
                    <hr className="my-1 border-surface-700/30" />
                    <button
                      onClick={() => { onDelete(source.id); setShowMenu(false); }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10"
                    >
                      <Trash2 className="h-4 w-4" /> Delete
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Status */}
          <div className="mt-2 flex items-center gap-2">
            <Badge variant={statusBadgeVariant(source.status)}>
              {source.status}
            </Badge>
            {source.chunk_count && (
              <span className="text-xs text-surface-500">{source.chunk_count} chunks</span>
            )}
            {source.page_count && (
              <span className="text-xs text-surface-500">{source.page_count} pages</span>
            )}
          </div>

          {/* Processing progress */}
          {isProcessing && (
            <div className="mt-3">
              <ProcessingProgress status={source.status} />
            </div>
          )}

          {/* Error message */}
          {source.status === 'FAILED' && source.error_message && (
            <p className="mt-2 text-xs text-red-400 bg-red-500/5 rounded-lg px-2 py-1.5 border border-red-500/10">
              {source.error_message}
            </p>
          )}
        </div>

        {/* Navigate arrow */}
        {source.status === 'READY' && (
          <button
            onClick={() => onSelect(source.id)}
            className="shrink-0 self-center opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <ChevronRight className="h-5 w-5 text-surface-500" />
          </button>
        )}
      </div>
    </div>
  );
}
