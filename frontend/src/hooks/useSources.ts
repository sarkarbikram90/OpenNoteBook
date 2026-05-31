/**
 * OpenNotebook — useSources hooks.
 *
 * TanStack Query wrappers for source CRUD + upload operations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSources,
  uploadFileSource,
  uploadUrlSource,
  deleteSource,
  reindexSource,
  triggerSummary,
} from '@/lib/api/sources';
import { addToast } from '@/stores/toast';

/** Query key factory for sources. */
export const sourceKeys = {
  all: (notebookId: string) => ['sources', notebookId] as const,
  detail: (notebookId: string, sourceId: string) =>
    ['sources', notebookId, sourceId] as const,
};

/** Fetch all sources for a notebook. */
export function useSources(notebookId: string) {
  return useQuery({
    queryKey: sourceKeys.all(notebookId),
    queryFn: () => getSources(notebookId),
    select: (data) => data.sources,
    enabled: !!notebookId,
    refetchInterval: 5000, // Poll for status updates
  });
}

/** Upload a file source. */
export function useUploadSource(notebookId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => uploadFileSource(notebookId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.all(notebookId) });
      addToast('info', 'Source uploaded', 'Processing has started');
    },
    onError: (error) => {
      addToast('error', 'Upload failed', error.message);
    },
  });
}

/** Upload a URL or YouTube source. */
export function useUploadUrlSource(notebookId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { url: string; source_type: 'url' | 'youtube'; name?: string }) =>
      uploadUrlSource(notebookId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.all(notebookId) });
      addToast('info', 'URL submitted', 'Processing has started');
    },
    onError: (error) => {
      addToast('error', 'URL upload failed', error.message);
    },
  });
}

/** Delete a source. */
export function useDeleteSource(notebookId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sourceId: string) => deleteSource(notebookId, sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.all(notebookId) });
      addToast('success', 'Source deleted');
    },
    onError: (error) => {
      addToast('error', 'Failed to delete source', error.message);
    },
  });
}

/** Re-index a source. */
export function useReindexSource(notebookId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sourceId: string) => reindexSource(notebookId, sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.all(notebookId) });
      addToast('info', 'Re-indexing started');
    },
    onError: (error) => {
      addToast('error', 'Re-index failed', error.message);
    },
  });
}

/** Trigger source summary generation. */
export function useTriggerSummary(notebookId: string) {
  return useMutation({
    mutationFn: (sourceId: string) => triggerSummary(notebookId, sourceId),
    onSuccess: () => {
      addToast('info', 'Summary generation started');
    },
    onError: (error) => {
      addToast('error', 'Failed to generate summary', error.message);
    },
  });
}
