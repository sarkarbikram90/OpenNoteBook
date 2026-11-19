/** OpenNotebook — TanStack Query hooks for Workspaces & RBAC. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  addWorkspaceMember,
  createWorkspace,
  listWorkspaceMembers,
  listWorkspaces,
  removeWorkspaceMember,
  updateWorkspace,
  updateWorkspaceMemberRole,
} from '@/lib/api/workspaces';
import { addToast } from '@/stores/toast';
import type {
  WorkspaceCreateRequest,
  WorkspaceRole,
  WorkspaceUpdateRequest,
} from '@/lib/types';

export function useWorkspaces() {
  return useQuery({
    queryKey: ['workspaces'],
    queryFn: listWorkspaces,
  });
}

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WorkspaceCreateRequest) => createWorkspace(data),
    onSuccess: (ws) => {
      qc.invalidateQueries({ queryKey: ['workspaces'] });
      addToast('success', 'Workspace created', ws.name);
    },
    onError: (err: Error) => {
      addToast('error', 'Failed to create workspace', err.message);
    },
  });
}

export function useUpdateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WorkspaceUpdateRequest }) =>
      updateWorkspace(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workspaces'] });
      addToast('success', 'Governance settings updated');
    },
    onError: (err: Error) => {
      addToast('error', 'Update failed', err.message);
    },
  });
}

export function useWorkspaceMembers(workspaceId: string | undefined) {
  return useQuery({
    queryKey: ['workspace-members', workspaceId],
    queryFn: () => listWorkspaceMembers(workspaceId!),
    enabled: Boolean(workspaceId),
  });
}

export function useAddWorkspaceMember(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ email, role }: { email: string; role: WorkspaceRole }) =>
      addWorkspaceMember(workspaceId, email, role),
    onSuccess: (member) => {
      qc.invalidateQueries({ queryKey: ['workspace-members', workspaceId] });
      qc.invalidateQueries({ queryKey: ['workspaces'] });
      addToast('success', 'Member added', `${member.email} (${member.role})`);
    },
    onError: (err: Error) => {
      addToast('error', 'Could not add member', err.message);
    },
  });
}

export function useUpdateWorkspaceMemberRole(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: WorkspaceRole }) =>
      updateWorkspaceMemberRole(workspaceId, userId, role),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workspace-members', workspaceId] });
      addToast('success', 'Role updated');
    },
    onError: (err: Error) => {
      addToast('error', 'Failed to update role', err.message);
    },
  });
}

export function useRemoveWorkspaceMember(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => removeWorkspaceMember(workspaceId, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workspace-members', workspaceId] });
      qc.invalidateQueries({ queryKey: ['workspaces'] });
      addToast('info', 'Member removed');
    },
    onError: (err: Error) => {
      addToast('error', 'Failed to remove member', err.message);
    },
  });
}
