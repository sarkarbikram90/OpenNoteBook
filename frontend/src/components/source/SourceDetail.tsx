/** OpenNotebook — Source detail view with metadata, summary, and suggested questions. */

import { FileText, Globe, Youtube, Calendar, Hash, Cpu, HelpCircle } from 'lucide-react';
import { Badge, statusBadgeVariant } from '@/components/ui/Badge';
import type { Source } from '@/lib/types';

interface SourceDetailProps {
  source: Source;
  onClose: () => void;
  onAskQuestion?: (question: string) => void;
}

export function SourceDetail({ source, onClose, onAskQuestion }: SourceDetailProps) {
  const typeIcon = {
    pdf: FileText,
    docx: FileText,
    txt: FileText,
    md: FileText,
    url: Globe,
    youtube: Youtube,
  }[source.source_type] || FileText;
  const TypeIcon = typeIcon;

  return (
    <div className="h-full overflow-y-auto border-l border-surface-700/30 bg-surface-900/50 w-80 p-5">
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-3">
          <TypeIcon className="h-5 w-5 text-primary-400" />
          <div>
            <h3 className="text-sm font-semibold text-surface-100">{source.name}</h3>
            <Badge variant={statusBadgeVariant(source.status)} className="mt-1">
              {source.status}
            </Badge>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1 text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-colors"
        >
          ✕
        </button>
      </div>

      {/* Metadata */}
      <div className="space-y-3 mb-6">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-surface-500">
          Details
        </h4>
        <div className="space-y-2">
          {source.page_count && (
            <MetaItem icon={Hash} label="Pages" value={source.page_count.toString()} />
          )}
          {source.chunk_count && (
            <MetaItem icon={Hash} label="Chunks" value={source.chunk_count.toString()} />
          )}
          {source.embedding_model && (
            <MetaItem icon={Cpu} label="Embedding model" value={source.embedding_model} />
          )}
          <MetaItem icon={FileText} label="Type" value={source.source_type.toUpperCase()} />
          <MetaItem
            icon={Calendar}
            label="Added"
            value={new Date(source.created_at).toLocaleDateString()}
          />
          {source.source_url && (
            <MetaItem icon={Globe} label="URL" value={source.source_url} />
          )}
        </div>
      </div>

      {/* Suggested questions placeholder */}
      {onAskQuestion && (
        <div className="space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-surface-500 flex items-center gap-1.5">
            <HelpCircle className="h-3.5 w-3.5" /> Suggested questions
          </h4>
          <div className="space-y-2">
            {['What is the main topic of this document?',
              'What are the key findings?',
              'Summarize the conclusions.',
            ].map((q, i) => (
              <button
                key={i}
                onClick={() => onAskQuestion(q)}
                className="w-full text-left rounded-lg border border-surface-700/30 bg-surface-800/40 px-3 py-2 text-xs text-surface-300 hover:bg-surface-800/70 hover:text-surface-100 transition-all"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MetaItem({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FileText;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <Icon className="h-3.5 w-3.5 text-surface-500 shrink-0" />
      <span className="text-surface-500">{label}</span>
      <span className="text-surface-300 truncate ml-auto">{value}</span>
    </div>
  );
}
