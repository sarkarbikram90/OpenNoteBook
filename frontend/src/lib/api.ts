/**
 * OpenNotebook — Base API client with JWT auth and auto-refresh.
 *
 * All API calls go through `apiFetch` which:
 * 1. Attaches the Bearer token from localStorage
 * 2. On 401, attempts a token refresh and retries once
 * 3. Returns typed JSON or throws an ApiError
 */

import { getTokens, setTokens, clearTokens } from '@/stores/auth';
import type { TokenResponse } from '@/lib/types';

const API_BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* response body not JSON */
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

async function refreshAccessToken(): Promise<string | null> {
  const tokens = getTokens();
  if (!tokens?.refresh_token) return null;

  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: tokens.refresh_token }),
    });

    if (!response.ok) {
      clearTokens();
      return null;
    }

    const data: TokenResponse = await response.json();
    setTokens(data);
    return data.access_token;
  } catch {
    clearTokens();
    return null;
  }
}

/**
 * Authenticated fetch wrapper.
 * Automatically attaches JWT, handles 401 refresh, and parses JSON.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const tokens = getTokens();
  const headers = new Headers(options.headers);

  if (tokens?.access_token) {
    headers.set('Authorization', `Bearer ${tokens.access_token}`);
  }

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;

  let response = await fetch(url, { ...options, headers });

  // Attempt refresh on 401
  if (response.status === 401 && tokens?.refresh_token) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set('Authorization', `Bearer ${newToken}`);
      response = await fetch(url, { ...options, headers });
    }
  }

  return handleResponse<T>(response);
}

/**
 * Streaming fetch for SSE endpoints (chat).
 * Returns the raw Response for manual ReadableStream consumption.
 */
export async function apiStreamFetch(
  path: string,
  body: Record<string, unknown>,
): Promise<Response> {
  const tokens = getTokens();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  };

  if (tokens?.access_token) {
    headers['Authorization'] = `Bearer ${tokens.access_token}`;
  }

  const url = `${API_BASE}${path}`;

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const errorBody = await response.json();
      detail = errorBody.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(response.status, detail);
  }

  return response;
}

/**
 * SSE EventSource wrapper for GET endpoints (source status).
 * Uses native EventSource since GET requests don't need auth body.
 */
export function apiEventSource(path: string): EventSource {
  const tokens = getTokens();
  const url = `${API_BASE}${path}`;

  // EventSource doesn't support custom headers natively.
  // For authenticated SSE GET endpoints, we pass the token as a query param.
  const separator = url.includes('?') ? '&' : '?';
  const fullUrl = tokens?.access_token
    ? `${url}${separator}token=${tokens.access_token}`
    : url;

  return new EventSource(fullUrl);
}
