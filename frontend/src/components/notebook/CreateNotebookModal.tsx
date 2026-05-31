/** OpenNotebook — Create notebook modal. */

import { useState, useCallback, type FormEvent } from 'react';
import { Loader2 } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';

interface CreateNotebookModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { name: string; description?: string }) => void;
  isLoading: boolean;
}

export function CreateNotebookModal({
  isOpen,
  onClose,
  onSubmit,
  isLoading,
}: CreateNotebookModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      if (!name.trim()) return;
      onSubmit({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setName('');
      setDescription('');
    },
    [name, description, onSubmit],
  );

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Notebook" size="sm">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm text-surface-300 mb-1.5" htmlFor="nb-name">
            Name
          </label>
          <input
            id="nb-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Research"
            autoFocus
            maxLength={255}
            className="w-full rounded-xl border border-surface-700/40 bg-surface-800/60 px-4 py-2.5 text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
          />
        </div>

        <div>
          <label className="block text-sm text-surface-300 mb-1.5" htmlFor="nb-desc">
            Description <span className="text-surface-500">(optional)</span>
          </label>
          <textarea
            id="nb-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="A collection of papers about..."
            rows={3}
            maxLength={2000}
            className="w-full rounded-xl border border-surface-700/40 bg-surface-800/60 px-4 py-2.5 text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 resize-none"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-xl border border-surface-700/40 bg-surface-800/40 py-2.5 text-sm font-medium text-surface-300 transition-colors hover:bg-surface-800"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!name.trim() || isLoading}
            className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-primary-600 py-2.5 text-sm font-medium text-white transition-all hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
            Create
          </button>
        </div>
      </form>
    </Modal>
  );
}
