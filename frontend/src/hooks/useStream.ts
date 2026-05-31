/**
 * OpenNotebook — useStream hook.
 *
 * EventSource wrapper for SSE chat streaming. Uses fetch + ReadableStream
 * (not native EventSource) because we need POST method + Authorization header.
 *
 * Handles four SSE event types:
 *   - token:    Individual generated tokens → appended to `content`
 *   - citation: Source citations referenced → appended to `citations`
 *   - done:     Generation complete with metadata
 *   - error:    An error occurred during generation
 *
 * Usage:
 *   const { content, citations, isStreaming, error, send, abort } = useStream();
 *   send(notebookId, question, { sessionId, sourceFilter });
 */

import { useState, useCallback, useRef } from 'react';
import { apiStreamFetch } from '@/lib/api';
import type { Citation, SSEDoneEvent } from '@/lib/types';

interface StreamState {
  /** Accumulated response text (grows token-by-token). */
  content: string;
  /** Citations collected during the stream. */
  citations: Citation[];
  /** Whether the stream is currently active. */
  isStreaming: boolean;
  /** Error message if the stream failed. */
  error: string | null;
  /** Message ID returned by the done event. */
  messageId: string | null;
  /** Latency in ms returned by the done event. */
  latencyMs: number | null;
}

interface SendOptions {
  sessionId?: string;
  sourceFilter?: string[];
}

interface UseStreamReturn extends StreamState {
  /** Start a new streaming request. */
  send: (notebookId: string, question: string, options?: SendOptions) => void;
  /** Abort the current stream. */
  abort: () => void;
  /** Reset state for a new message. */
  reset: () => void;
}

const initialState: StreamState = {
  content: '',
  citations: [],
  isStreaming: false,
  error: null,
  messageId: null,
  latencyMs: null,
};

/**
 * Parse SSE lines from a text chunk.
 *
 * SSE format:
 *   event: <type>\n
 *   data: <json>\n
 *   \n
 */
function parseSSEEvents(buffer: string): {
  events: Array<{ event: string; data: string }>;
  remaining: string;
} {
  const events: Array<{ event: string; data: string }> = [];
  const lines = buffer.split('\n');
  let currentEvent = '';
  let currentData = '';
  let remaining = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('event: ')) {
      currentEvent = line.slice(7).trim();
    } else if (line.startsWith('data: ')) {
      currentData = line.slice(6);
    } else if (line === '' && currentEvent) {
      events.push({ event: currentEvent, data: currentData });
      currentEvent = '';
      currentData = '';
    } else if (i === lines.length - 1 && line !== '') {
      // Incomplete line — keep in buffer
      remaining = line;
    }
  }

  // If we have a partial event in progress, put it back
  if (currentEvent) {
    remaining =
      `event: ${currentEvent}\n` +
      (currentData ? `data: ${currentData}\n` : '') +
      remaining;
  }

  return { events, remaining };
}

export function useStream(): UseStreamReturn {
  const [state, setState] = useState<StreamState>(initialState);
  const abortControllerRef = useRef<AbortController | null>(null);

  const abort = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setState((prev) => ({ ...prev, isStreaming: false }));
  }, []);

  const reset = useCallback(() => {
    abort();
    setState(initialState);
  }, [abort]);

  const send = useCallback(
    async (notebookId: string, question: string, options?: SendOptions) => {
      // Abort any existing stream
      abortControllerRef.current?.abort();

      const controller = new AbortController();
      abortControllerRef.current = controller;

      setState({
        content: '',
        citations: [],
        isStreaming: true,
        error: null,
        messageId: null,
        latencyMs: null,
      });

      try {
        const body: Record<string, unknown> = { question };
        if (options?.sessionId) body.session_id = options.sessionId;
        if (options?.sourceFilter) body.source_filter = options.sourceFilter;

        const response = await apiStreamFetch(
          `/notebooks/${notebookId}/chat`,
          body,
        );

        if (!response.body) {
          throw new Error('No response body for SSE stream');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();

          if (controller.signal.aborted) {
            reader.cancel();
            break;
          }

          if (done) {
            // Process any remaining buffer
            if (buffer.trim()) {
              const { events } = parseSSEEvents(buffer + '\n\n');
              for (const evt of events) {
                processEvent(evt.event, evt.data, setState);
              }
            }
            setState((prev) => ({ ...prev, isStreaming: false }));
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const { events, remaining } = parseSSEEvents(buffer);
          buffer = remaining;

          for (const evt of events) {
            processEvent(evt.event, evt.data, setState);
          }
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          const message = err instanceof Error ? err.message : 'Stream failed';
          setState((prev) => ({
            ...prev,
            isStreaming: false,
            error: message,
          }));
        }
      }
    },
    [],
  );

  return { ...state, send, abort, reset };
}

/** Process a single SSE event and update state. */
function processEvent(
  eventType: string,
  data: string,
  setState: React.Dispatch<React.SetStateAction<StreamState>>,
): void {
  switch (eventType) {
    case 'token': {
      try {
        const parsed = JSON.parse(data) as { token: string };
        setState((prev) => ({
          ...prev,
          content: prev.content + parsed.token,
        }));
      } catch {
        // Malformed token event — append raw data
        setState((prev) => ({
          ...prev,
          content: prev.content + data,
        }));
      }
      break;
    }

    case 'citation': {
      try {
        const parsed = JSON.parse(data) as Citation;
        setState((prev) => ({
          ...prev,
          citations: [...prev.citations, parsed],
        }));
      } catch {
        /* ignore malformed citation */
      }
      break;
    }

    case 'done': {
      try {
        const parsed = JSON.parse(data) as SSEDoneEvent;
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          messageId: parsed.message_id,
          latencyMs: parsed.latency_ms,
        }));
      } catch {
        setState((prev) => ({ ...prev, isStreaming: false }));
      }
      break;
    }

    case 'error': {
      try {
        const parsed = JSON.parse(data) as { code: string; message: string };
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          error: parsed.message || parsed.code,
        }));
      } catch {
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          error: data || 'Unknown error',
        }));
      }
      break;
    }
  }
}
