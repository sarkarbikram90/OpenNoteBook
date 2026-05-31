/**
 * OpenNotebook — useChat hooks.
 *
 * TanStack Query hooks for chat sessions and messages.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSessions,
  getMessages,
  deleteSession,
  exportSession,
} from '@/lib/api/chat';
import { addToast } from '@/stores/toast';

/** Query key factory for chat. */
export const chatKeys = {
  sessions: (notebookId: string) => ['sessions', notebookId] as const,
  messages: (sessionId: string) => ['messages', sessionId] as const,
};

/** Fetch all chat sessions for a notebook. */
export function useSessions(notebookId: string) {
  return useQuery({
    queryKey: chatKeys.sessions(notebookId),
    queryFn: () => getSessions(notebookId),
    select: (data) => data.sessions,
    enabled: !!notebookId,
  });
}

/** Fetch all messages in a chat session. */
export function useMessages(sessionId: string | null) {
  return useQuery({
    queryKey: chatKeys.messages(sessionId ?? ''),
    queryFn: () => getMessages(sessionId!),
    select: (data) => data.messages,
    enabled: !!sessionId,
  });
}

/** Delete a chat session. */
export function useDeleteSession(notebookId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chatKeys.sessions(notebookId) });
      addToast('success', 'Chat session deleted');
    },
    onError: (error) => {
      addToast('error', 'Failed to delete session', error.message);
    },
  });
}

/** Export a chat session as markdown or PDF. */
export function useExportSession() {
  return useMutation({
    mutationFn: ({
      sessionId,
      format,
    }: {
      sessionId: string;
      format: 'markdown' | 'pdf';
    }) => exportSession(sessionId, format),
    onSuccess: (blob, variables) => {
      // Trigger browser download
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `chat-export.${variables.format === 'pdf' ? 'pdf' : 'md'}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      addToast('success', 'Session exported');
    },
    onError: (error) => {
      addToast('error', 'Export failed', error.message);
    },
  });
}
