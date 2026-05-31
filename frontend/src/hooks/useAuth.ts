/**
 * OpenNotebook — useAuth hook.
 *
 * Provides authentication context: login, register, logout, current user.
 * Uses TanStack Query for the /auth/me call (no useEffect for data fetching).
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { login, register, getMe, logout } from '@/lib/api/auth';
import { setTokens, clearTokens, isAuthenticated, setCurrentUser } from '@/stores/auth';
import { addToast } from '@/stores/toast';

export const authKeys = {
  me: ['auth', 'me'] as const,
};

/** Fetch the current user profile (only if authenticated). */
export function useCurrentUser() {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: async () => {
      const user = await getMe();
      setCurrentUser(user);
      return user;
    },
    enabled: isAuthenticated(),
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/** Login mutation. */
export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      login(email, password),
    onSuccess: (tokens) => {
      setTokens(tokens);
      queryClient.invalidateQueries({ queryKey: authKeys.me });
      addToast('success', 'Welcome back!');
    },
    onError: (error) => {
      addToast('error', 'Login failed', error.message);
    },
  });
}

/** Register mutation. */
export function useRegister() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      register(email, password),
    onSuccess: (tokens) => {
      setTokens(tokens);
      queryClient.invalidateQueries({ queryKey: authKeys.me });
      addToast('success', 'Account created!');
    },
    onError: (error) => {
      addToast('error', 'Registration failed', error.message);
    },
  });
}

/** Logout — clears tokens and query cache. */
export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      try {
        await logout();
      } catch {
        /* best-effort server-side revoke */
      }
      clearTokens();
      setCurrentUser(null);
      queryClient.clear();
    },
  });
}
