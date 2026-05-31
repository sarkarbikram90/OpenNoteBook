/** OpenNotebook — Chat API functions. */

import { apiFetch } from '@/lib/api';
import type {
  ChatSessionListResponse,
  ChatSession,
  MessageListResponse,
} from '@/lib/types';

export async function getSessions(notebookId: string): Promise<ChatSessionListResponse> {
  return apiFetch<ChatSessionListResponse>(`/notebooks/${notebookId}/sessions`);
}

export async function getSession(sessionId: string): Promise<ChatSession> {
  return apiFetch<ChatSession>(`/sessions/${sessionId}`);
}

export async function getMessages(sessionId: string): Promise<MessageListResponse> {
  return apiFetch<MessageListResponse>(`/sessions/${sessionId}/messages`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  return apiFetch<void>(`/sessions/${sessionId}`, { method: 'DELETE' });
}

export async function exportSession(
  sessionId: string,
  format: 'markdown' | 'pdf' = 'markdown',
): Promise<Blob> {
  const tokens = await import('@/stores/auth').then((m) => m.getTokens());
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (tokens?.access_token) {
    headers['Authorization'] = `Bearer ${tokens.access_token}`;
  }

  const response = await fetch(`/api/v1/sessions/${sessionId}/export`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ format }),
  });

  if (!response.ok) {
    throw new Error(`Export failed: HTTP ${response.status}`);
  }

  return response.blob();
}
