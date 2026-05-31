/**
 * OpenNotebook — useSourceStatus hook.
 *
 * SSE hook for real-time source processing status updates.
 * Subscribes to GET /api/v1/notebooks/{id}/sources/{sourceId}/status
 */

import { useState, useEffect, useRef } from 'react';
import type { SourceStatus, SourceStatusEvent } from '@/lib/types';

interface SourceStatusState {
  status: SourceStatus;
  chunkCount: number | null;
  errorMessage: string | null;
  isConnected: boolean;
}

/**
 * Subscribe to real-time status updates for a source being processed.
 *
 * @param notebookId - Notebook UUID
 * @param sourceId - Source UUID
 * @param enabled - Whether to connect (false to skip connecting)
 */
export function useSourceStatus(
  notebookId: string,
  sourceId: string,
  enabled = true,
): SourceStatusState {
  const [state, setState] = useState<SourceStatusState>({
    status: 'PENDING',
    chunkCount: null,
    errorMessage: null,
    isConnected: false,
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled || !notebookId || !sourceId) return;

    const url = `/api/v1/notebooks/${notebookId}/sources/${sourceId}/status`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    setState((prev) => ({ ...prev, isConnected: true }));

    es.addEventListener('status', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as SourceStatusEvent;
        setState({
          status: data.status,
          chunkCount: data.chunk_count ?? null,
          errorMessage: data.error_message ?? null,
          isConnected: true,
        });
      } catch {
        /* ignore malformed events */
      }
    });

    es.addEventListener('done', () => {
      es.close();
      setState((prev) => ({ ...prev, isConnected: false }));
    });

    es.onerror = () => {
      es.close();
      setState((prev) => ({ ...prev, isConnected: false }));
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [notebookId, sourceId, enabled]);

  return state;
}
