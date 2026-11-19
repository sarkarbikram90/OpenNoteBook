/** OpenNotebook — TanStack Query hooks for Studio (Audio Overviews & Knowledge Graph). */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAudioOverview,
  deleteAudioOverview,
  getKnowledgeGraph,
  listAudioOverviews,
} from '@/lib/api/studio';
import { addToast } from '@/stores/toast';
import type { AudioOverviewCreateRequest } from '@/lib/types';

export function useAudioOverviews(notebookId: string) {
  return useQuery({
    queryKey: ['audio-overviews', notebookId],
    queryFn: () => listAudioOverviews(notebookId),
    enabled: Boolean(notebookId),
  });
}

export function useCreateAudioOverview(notebookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AudioOverviewCreateRequest) =>
      createAudioOverview(notebookId, data),
    onSuccess: (overview) => {
      qc.invalidateQueries({ queryKey: ['audio-overviews', notebookId] });
      addToast('success', 'Audio Overview ready', overview.title);
    },
    onError: (err: Error) => {
      addToast('error', 'Generation failed', err.message);
    },
  });
}

export function useDeleteAudioOverview(notebookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (overviewId: string) => deleteAudioOverview(notebookId, overviewId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['audio-overviews', notebookId] });
      addToast('info', 'Audio Overview deleted');
    },
    onError: (err: Error) => {
      addToast('error', 'Delete failed', err.message);
    },
  });
}

export function useKnowledgeGraph(notebookId: string, query?: string) {
  return useQuery({
    queryKey: ['knowledge-graph', notebookId, query ?? ''],
    queryFn: () => getKnowledgeGraph(notebookId, query),
    enabled: Boolean(notebookId),
  });
}
