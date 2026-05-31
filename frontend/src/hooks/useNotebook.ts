/**
 * OpenNotebook — useNotebook hooks.
 *
 * TanStack Query wrappers for notebook CRUD operations.
 * No useEffect for data fetching — all via useQuery/useMutation.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getNotebooks,
  getNotebook,
  createNotebook,
  updateNotebook,
  deleteNotebook,
} from '@/lib/api/notebooks';
import { addToast } from '@/stores/toast';

/** Query key factory for notebooks. */
export const notebookKeys = {
  all: ['notebooks'] as const,
  detail: (id: string) => ['notebooks', id] as const,
};

/** Fetch all notebooks for the current user. */
export function useNotebooks() {
  return useQuery({
    queryKey: notebookKeys.all,
    queryFn: getNotebooks,
    select: (data) => data.notebooks,
  });
}

/** Fetch a single notebook by ID. */
export function useNotebook(id: string) {
  return useQuery({
    queryKey: notebookKeys.detail(id),
    queryFn: () => getNotebook(id),
    enabled: !!id,
  });
}

/** Create a new notebook. */
export function useCreateNotebook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createNotebook,
    onSuccess: (notebook) => {
      queryClient.invalidateQueries({ queryKey: notebookKeys.all });
      addToast('success', 'Notebook created', `"${notebook.name}" is ready`);
    },
    onError: (error) => {
      addToast('error', 'Failed to create notebook', error.message);
    },
  });
}

/** Update notebook name/description. */
export function useUpdateNotebook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; name?: string; description?: string }) =>
      updateNotebook(id, data),
    onSuccess: (notebook) => {
      queryClient.invalidateQueries({ queryKey: notebookKeys.all });
      queryClient.invalidateQueries({ queryKey: notebookKeys.detail(notebook.id) });
    },
    onError: (error) => {
      addToast('error', 'Failed to update notebook', error.message);
    },
  });
}

/** Delete a notebook. */
export function useDeleteNotebook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteNotebook,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notebookKeys.all });
      addToast('success', 'Notebook deleted');
    },
    onError: (error) => {
      addToast('error', 'Failed to delete notebook', error.message);
    },
  });
}
