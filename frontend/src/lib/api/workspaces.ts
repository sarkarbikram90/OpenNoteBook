/** OpenNotebook — Workspaces & RBAC API client. */

import { apiFetch } from '@/lib/api';
import type {
  Workspace,
  WorkspaceCreateRequest,
  WorkspaceMember,
  WorkspaceRole,
  WorkspaceUpdateRequest,
} from '@/lib/types';

export function listWorkspaces(): Promise<Workspace[]> {
  return apiFetch<Workspace[]>('/workspaces');
}

export function createWorkspace(data: WorkspaceCreateRequest): Promise<Workspace> {
  return apiFetch<Workspace>('/workspaces', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateWorkspace(
  workspaceId: string,
  data: WorkspaceUpdateRequest,
): Promise<Workspace> {
  return apiFetch<Workspace>(`/workspaces/${workspaceId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function listWorkspaceMembers(workspaceId: string): Promise<WorkspaceMember[]> {
  return apiFetch<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`);
}

export function addWorkspaceMember(
  workspaceId: string,
  email: string,
  role: WorkspaceRole,
): Promise<WorkspaceMember> {
  return apiFetch<WorkspaceMember>(`/workspaces/${workspaceId}/members`, {
    method: 'POST',
    body: JSON.stringify({ email, role }),
  });
}

export function updateWorkspaceMemberRole(
  workspaceId: string,
  memberUserId: string,
  role: WorkspaceRole,
): Promise<WorkspaceMember> {
  return apiFetch<WorkspaceMember>(
    `/workspaces/${workspaceId}/members/${memberUserId}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    },
  );
}

export function removeWorkspaceMember(
  workspaceId: string,
  memberUserId: string,
): Promise<void> {
  return apiFetch<void>(`/workspaces/${workspaceId}/members/${memberUserId}`, {
    method: 'DELETE',
  });
}
