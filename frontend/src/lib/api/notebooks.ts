/** OpenNotebook — Notebooks API functions. */

import { apiFetch } from '@/lib/api';
import type { Notebook, NotebookListResponse } from '@/lib/types';

export async function getNotebooks(): Promise<NotebookListResponse> {
  return apiFetch<NotebookListResponse>('/notebooks');
}

export async function getNotebook(id: string): Promise<Notebook> {
  return apiFetch<Notebook>(`/notebooks/${id}`);
}

export async function createNotebook(data: {
  name: string;
  description?: string;
}): Promise<Notebook> {
  return apiFetch<Notebook>('/notebooks', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateNotebook(
  id: string,
  data: { name?: string; description?: string },
): Promise<Notebook> {
  return apiFetch<Notebook>(`/notebooks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteNotebook(id: string): Promise<void> {
  return apiFetch<void>(`/notebooks/${id}`, { method: 'DELETE' });
}
