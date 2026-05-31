/** OpenNotebook — Settings API functions. */

import { apiFetch } from '@/lib/api';
import type { Settings, SettingsUpdate } from '@/lib/types';

export async function getSettings(): Promise<Settings> {
  return apiFetch<Settings>('/settings');
}

export async function updateSettings(data: SettingsUpdate): Promise<Settings> {
  return apiFetch<Settings>('/settings', {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}
