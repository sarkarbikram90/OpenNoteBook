/** OpenNotebook — Source library with upload, list, and detail view. */

import { useState, useCallback } from 'react';
import { Plus, Search, FolderOpen } from 'lucide-react';
import { useSources, useUploadSource, useUploadUrlSource, useDeleteSource, useReindexSource, useTriggerSummary } from '@/hooks/useSources';
import { SourceCard } from '@/components/source/SourceCard';
import { SourceDetail } from '@/components/source/SourceDetail';
import { UploadModal } from '@/components/source/UploadModal';
import { Spinner } from '@/components/ui/Spinner';

interface SourceLibraryProps {
  notebookId: string;
  onAskQuestion?: (question: string) => void;
}

export function SourceLibrary({ notebookId, onAskQuestion }: SourceLibraryProps) {
  const [showUpload, setShowUpload] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const { data: sources = [], isLoading } = useSources(notebookId);
  const uploadMutation = useUploadSource(notebookId);
  const uploadUrlMutation = useUploadUrlSource(notebookId);
  const deleteMutation = useDeleteSource(notebookId);
  const reindexMutation = useReindexSource(notebookId);
  const summarizeMutation = useTriggerSummary(notebookId);

  const selectedSource = sources.find((s) => s.id === selectedSourceId);

  const filteredSources = sources.filter((s) =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const handleUploadFiles = useCallback(
    (files: File[]) => {
      files.forEach((file) => uploadMutation.mutate(file));
      setShowUpload(false);
    },
    [uploadMutation],
  );

  const handleUploadUrl = useCallback(
    (url: string, type: 'url' | 'youtube', name?: string) => {
      uploadUrlMutation.mutate({ url, source_type: type, name });
      setShowUpload(false);
    },
    [uploadUrlMutation],
  );

  return (
    <div className="flex h-full">
      {/* Main list */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-700/30 px-6 py-3">
          <h2 className="text-sm font-semibold text-surface-200">Sources</h2>
          <button
            onClick={() => setShowUpload(true)}
            className="flex items-center gap-1.5 rounded-xl bg-primary-600 px-3.5 py-1.5 text-xs font-medium text-white transition-all hover:bg-primary-500 shadow-md shadow-primary-500/20 active:scale-95"
          >
            <Plus className="h-3.5 w-3.5" />
            Add source
          </button>
        </div>

        {/* Search */}
        {sources.length > 0 && (
          <div className="px-6 py-3 border-b border-surface-700/20">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-surface-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search sources..."
                className="w-full rounded-lg border border-surface-700/30 bg-surface-800/40 pl-9 pr-4 py-2 text-sm text-surface-200 placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
              />
            </div>
          </div>
        )}

        {/* Source list */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <Spinner size="lg" />
            </div>
          ) : filteredSources.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <FolderOpen className="h-14 w-14 text-surface-600 mb-4" />
              <h3 className="text-base font-medium text-surface-300 mb-1">
                {sources.length === 0 ? 'No sources yet' : 'No matching sources'}
              </h3>
              <p className="text-sm text-surface-500 max-w-sm">
                {sources.length === 0
                  ? 'Upload PDFs, documents, or paste URLs to build your knowledge base.'
                  : 'Try adjusting your search query.'}
              </p>
              {sources.length === 0 && (
                <button
                  onClick={() => setShowUpload(true)}
                  className="mt-4 flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-all hover:bg-primary-500"
                >
                  <Plus className="h-4 w-4" />
                  Add your first source
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {filteredSources.map((source) => (
                <SourceCard
                  key={source.id}
                  source={source}
                  onDelete={(id) => deleteMutation.mutate(id)}
                  onReindex={(id) => reindexMutation.mutate(id)}
                  onSummarize={(id) => summarizeMutation.mutate(id)}
                  onSelect={setSelectedSourceId}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Detail panel */}
      {selectedSource && (
        <SourceDetail
          source={selectedSource}
          onClose={() => setSelectedSourceId(null)}
          onAskQuestion={onAskQuestion}
        />
      )}

      {/* Upload modal */}
      <UploadModal
        isOpen={showUpload}
        onClose={() => setShowUpload(false)}
        onUploadFiles={handleUploadFiles}
        onUploadUrl={handleUploadUrl}
        isUploading={uploadMutation.isPending || uploadUrlMutation.isPending}
      />
    </div>
  );
}
