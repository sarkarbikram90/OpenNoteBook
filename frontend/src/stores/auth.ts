/**
 * OpenNotebook — Auth store.
 *
 * Simple module-level token/user state with localStorage persistence.
 * No external state library needed — React components use useAuth hook.
 */

import type { TokenResponse, User } from '@/lib/types';

const TOKEN_KEY = 'opennotebook_tokens';

/** Get stored tokens from localStorage. */
export function getTokens(): TokenResponse | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as TokenResponse;
  } catch {
    return null;
  }
}

/** Store tokens in localStorage. */
export function setTokens(tokens: TokenResponse): void {
  localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
}

/** Remove tokens from localStorage. */
export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/** Check if user has stored tokens (may be expired). */
export function isAuthenticated(): boolean {
  return getTokens() !== null;
}

/**
 * Decode the JWT payload to extract basic claims.
 * This does NOT verify the signature — only used for client-side display.
 */
export function decodeTokenPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(payload) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** In-memory user cache (set after /auth/me call). */
let currentUser: User | null = null;

export function setCurrentUser(user: User | null): void {
  currentUser = user;
}

export function getCurrentUser(): User | null {
  return currentUser;
}
