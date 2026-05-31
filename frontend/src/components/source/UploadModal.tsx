/** OpenNotebook — Upload modal with drag & drop and URL input. */

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { clsx } from 'clsx';
import { Upload, Link, Youtube, X, FileText, Loader2 } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadFiles: (files: File[]) => void;
  onUploadUrl: (url: string, type: 'url' | 'youtube', name?: string) => void;
  isUploading: boolean;
}

type Tab = 'file' | 'url';

const ACCEPT = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'text/markdown': ['.md'],
};

export function UploadModal({
  isOpen,
  onClose,
  onUploadFiles,
  onUploadUrl,
  isUploading,
}: UploadModalProps) {
  const [tab, setTab] = useState<Tab>('file');
  const [urlInput, setUrlInput] = useState('');
  const [urlName, setUrlName] = useState('');
  const [droppedFiles, setDroppedFiles] = useState<File[]>([]);

  const onDrop = useCallback((accepted: File[]) => {
    setDroppedFiles((prev) => [...prev, ...accepted]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPT,
    maxSize: 50 * 1024 * 1024, // 50MB
    multiple: true,
    maxFiles: 10,
  });

  const isYoutube = urlInput.includes('youtube.com') || urlInput.includes('youtu.be');

  const handleUploadFiles = () => {
    if (droppedFiles.length === 0) return;
    onUploadFiles(droppedFiles);
    setDroppedFiles([]);
  };

  const handleUploadUrl = () => {
    if (!urlInput.trim()) return;
    onUploadUrl(urlInput.trim(), isYoutube ? 'youtube' : 'url', urlName || undefined);
    setUrlInput('');
    setUrlName('');
  };

  const removeFile = (index: number) => {
    setDroppedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Sources" size="lg">
      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-surface-800/60 p-1 mb-5">
        {([['file', Upload, 'Upload Files'], ['url', Link, 'URL / YouTube']] as const).map(
          ([key, Icon, label]) => (
            <button
              key={key}
              onClick={() => setTab(key as Tab)}
              className={clsx(
                'flex-1 flex items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition-all',
                tab === key
                  ? 'bg-primary-600 text-white shadow-md'
                  : 'text-surface-400 hover:text-surface-200',
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ),
        )}
      </div>

      {tab === 'file' ? (
        <div>
          {/* Drop zone */}
          <div
            {...getRootProps()}
            className={clsx(
              'flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-all cursor-pointer',
              isDragActive
                ? 'border-primary-500 bg-primary-500/5'
                : 'border-surface-600/40 hover:border-surface-500/60 hover:bg-surface-800/30',
            )}
          >
            <input {...getInputProps()} />
            <Upload
              className={clsx(
                'h-10 w-10 mb-3',
                isDragActive ? 'text-primary-400' : 'text-surface-500',
              )}
            />
            <p className="text-sm text-surface-300 font-medium">
              {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
            </p>
            <p className="text-xs text-surface-500 mt-1">
              PDF, DOCX, TXT, Markdown · Max 50MB each
            </p>
          </div>

          {/* File list */}
          {droppedFiles.length > 0 && (
            <div className="mt-4 space-y-2">
              {droppedFiles.map((file, i) => (
                <div
                  key={`${file.name}-${i}`}
                  className="flex items-center justify-between rounded-lg border border-surface-700/30 bg-surface-800/40 px-3 py-2"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-4 w-4 text-surface-400 shrink-0" />
                    <span className="text-sm text-surface-200 truncate">{file.name}</span>
                    <span className="text-xs text-surface-500 shrink-0">
                      {(file.size / 1024 / 1024).toFixed(1)}MB
                    </span>
                  </div>
                  <button
                    onClick={() => removeFile(i)}
                    className="rounded p-1 text-surface-500 hover:text-red-400 transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}

              <button
                onClick={handleUploadFiles}
                disabled={isUploading}
                className="w-full mt-3 flex items-center justify-center gap-2 rounded-xl bg-primary-600 py-2.5 text-sm font-medium text-white transition-all hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isUploading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                Upload {droppedFiles.length} file{droppedFiles.length > 1 ? 's' : ''}
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-surface-300 mb-1.5">URL</label>
            <div className="relative">
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://example.com/article or YouTube URL"
                className="w-full rounded-xl border border-surface-700/40 bg-surface-800/60 px-4 py-2.5 pl-10 text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
              />
              {isYoutube ? (
                <Youtube className="absolute left-3 top-3 h-4 w-4 text-red-400" />
              ) : (
                <Link className="absolute left-3 top-3 h-4 w-4 text-surface-500" />
              )}
            </div>
            {isYoutube && (
              <p className="mt-1.5 text-xs text-amber-400">
                YouTube video detected — will extract transcript
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm text-surface-300 mb-1.5">
              Display name <span className="text-surface-500">(optional)</span>
            </label>
            <input
              type="text"
              value={urlName}
              onChange={(e) => setUrlName(e.target.value)}
              placeholder="My article"
              className="w-full rounded-xl border border-surface-700/40 bg-surface-800/60 px-4 py-2.5 text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
            />
          </div>

          <button
            onClick={handleUploadUrl}
            disabled={!urlInput.trim() || isUploading}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary-600 py-2.5 text-sm font-medium text-white transition-all hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Link className="h-4 w-4" />
            )}
            Add source
          </button>
        </div>
      )}
    </Modal>
  );
}
