/**
 * OpenNotebook — useSettings hook.
 *
 * TanStack Query hooks for user settings / model registry.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, updateSettings } from '@/lib/api/settings';
import type { SettingsUpdate } from '@/lib/types';
import { addToast } from '@/stores/toast';

export const settingsKeys = {
  all: ['settings'] as const,
};

/** Fetch current user's settings. */
export function useSettings() {
  return useQuery({
    queryKey: settingsKeys.all,
    queryFn: getSettings,
  });
}

/** Update user settings with optimistic update. */
export function useUpdateSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SettingsUpdate) => updateSettings(data),
    onSuccess: (updated) => {
      queryClient.setQueryData(settingsKeys.all, updated);
      addToast('success', 'Settings saved');
    },
    onError: (error) => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.all });
      addToast('error', 'Failed to save settings', error.message);
    },
  });
}
