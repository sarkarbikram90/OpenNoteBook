/** OpenNotebook — Studio API client (Audio Overviews & Knowledge Graph). */

import { apiFetch } from '@/lib/api';
import type {
  AudioOverview,
  AudioOverviewCreateRequest,
  KnowledgeGraph,
} from '@/lib/types';

export function listAudioOverviews(notebookId: string): Promise<AudioOverview[]> {
  return apiFetch<AudioOverview[]>(`/notebooks/${notebookId}/studio/audio-overviews`);
}

export function createAudioOverview(
  notebookId: string,
  data: AudioOverviewCreateRequest,
): Promise<AudioOverview> {
  return apiFetch<AudioOverview>(`/notebooks/${notebookId}/studio/audio-overviews`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function deleteAudioOverview(
  notebookId: string,
  overviewId: string,
): Promise<void> {
  return apiFetch<void>(
    `/notebooks/${notebookId}/studio/audio-overviews/${overviewId}`,
    { method: 'DELETE' },
  );
}

export function getKnowledgeGraph(
  notebookId: string,
  query?: string,
): Promise<KnowledgeGraph> {
  const qs = query && query.trim() ? `?query=${encodeURIComponent(query.trim())}` : '';
  return apiFetch<KnowledgeGraph>(
    `/notebooks/${notebookId}/studio/knowledge-graph${qs}`,
  );
}
