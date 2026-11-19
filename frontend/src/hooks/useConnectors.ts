/** OpenNotebook — TanStack Query hooks for Enterprise Connectors. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createConnector,
  deleteConnector,
  listConnectors,
  syncConnector,
  testConnector,
} from '@/lib/api/connectors';
import { addToast } from '@/stores/toast';
import type { ConnectorCreateRequest } from '@/lib/types';

export function useConnectors(workspaceId: string | undefined) {
  return useQuery({
    queryKey: ['connectors', workspaceId],
    queryFn: () => listConnectors(workspaceId!),
    enabled: Boolean(workspaceId),
  });
}

export function useCreateConnector(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ConnectorCreateRequest) => createConnector(data),
    onSuccess: (conn) => {
      qc.invalidateQueries({ queryKey: ['connectors', workspaceId] });
      addToast('success', 'Connector created', `${conn.name} (${conn.connector_type})`);
    },
    onError: (err: Error) => {
      addToast('error', 'Failed to create connector', err.message);
    },
  });
}

export function useTestConnector() {
  return useMutation({
    mutationFn: (connectorId: string) => testConnector(connectorId),
    onSuccess: (res) => {
      if (res.success) {
        addToast('success', 'Connection verified', res.message);
      } else {
        addToast('warning', 'Connection check failed', res.message);
      }
    },
    onError: (err: Error) => {
      addToast('error', 'Connection test error', err.message);
    },
  });
}

export function useSyncConnector(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (connectorId: string) => syncConnector(connectorId),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['connectors', workspaceId] });
      addToast(
        'success',
        'Connector sync triggered',
        `${res.documents_synced} new document(s) queued for ingestion`,
      );
    },
    onError: (err: Error) => {
      addToast('error', 'Sync failed', err.message);
    },
  });
}

export function useDeleteConnector(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (connectorId: string) => deleteConnector(connectorId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['connectors', workspaceId] });
      addToast('info', 'Connector removed');
    },
    onError: (err: Error) => {
      addToast('error', 'Delete failed', err.message);
    },
  });
}
