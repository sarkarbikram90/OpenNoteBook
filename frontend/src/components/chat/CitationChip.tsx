/** OpenNotebook — Inline citation chip with hover tooltip. */

import { useState } from 'react';
import { clsx } from 'clsx';
import { FileText } from 'lucide-react';
import type { Citation } from '@/lib/types';

interface CitationChipProps {
  citation: Citation;
  index: number;
}

export function CitationChip({ citation, index }: CitationChipProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <span className="relative inline-flex">
      <button
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={() => setShowTooltip(!showTooltip)}
        className={clsx(
          'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium',
          'bg-primary-500/15 text-primary-300 border border-primary-500/25',
          'hover:bg-primary-500/25 transition-colors cursor-pointer',
        )}
      >
        <FileText className="h-3 w-3" />
        Source {index + 1}
      </button>

      {showTooltip && (
        <div
          className={clsx(
            'absolute bottom-full left-0 mb-2 z-50 w-72',
            'rounded-xl border border-surface-700/50 bg-surface-800 p-3 shadow-xl shadow-black/30',
            'animate-fade-in',
          )}
        >
          <div className="flex items-start gap-2">
            <FileText className="h-4 w-4 text-primary-400 mt-0.5 shrink-0" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-surface-100 truncate">
                {citation.source_name}
              </p>
              {citation.page && (
                <p className="text-xs text-surface-400 mt-0.5">
                  Page {citation.page}
                </p>
              )}
              {citation.section && (
                <p className="text-xs text-surface-400 mt-0.5">
                  § {citation.section}
                </p>
              )}
              {citation.relevance_score > 0 && (
                <div className="mt-2 flex items-center gap-2">
                  <div className="flex-1 h-1.5 rounded-full bg-surface-700 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-primary-500 to-primary-400"
                      style={{ width: `${Math.round(citation.relevance_score * 100)}%` }}
                    />
                  </div>
                  <span className="text-xs text-surface-500">
                    {Math.round(citation.relevance_score * 100)}%
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </span>
  );
}

/** Render citation chips from a list. */
export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  // Deduplicate by chunk_id
  const seen = new Set<string>();
  const unique = citations.filter((c) => {
    if (seen.has(c.chunk_id)) return false;
    seen.add(c.chunk_id);
    return true;
  });

  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {unique.map((citation, i) => (
        <CitationChip key={citation.chunk_id} citation={citation} index={i} />
      ))}
    </div>
  );
}
