/** OpenNotebook — Enterprise Connectors API client. */

import { apiFetch } from '@/lib/api';
import type {
  Connector,
  ConnectorCreateRequest,
  ConnectorSyncResponse,
  ConnectorTestResponse,
} from '@/lib/types';

export function listConnectors(workspaceId: string): Promise<Connector[]> {
  return apiFetch<Connector[]>(
    `/connectors?workspace_id=${encodeURIComponent(workspaceId)}`,
  );
}

export function createConnector(data: ConnectorCreateRequest): Promise<Connector> {
  return apiFetch<Connector>('/connectors', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function testConnector(connectorId: string): Promise<ConnectorTestResponse> {
  return apiFetch<ConnectorTestResponse>(`/connectors/${connectorId}/test`, {
    method: 'POST',
  });
}

export function syncConnector(connectorId: string): Promise<ConnectorSyncResponse> {
  return apiFetch<ConnectorSyncResponse>(`/connectors/${connectorId}/sync`, {
    method: 'POST',
  });
}

export function deleteConnector(connectorId: string): Promise<void> {
  return apiFetch<void>(`/connectors/${connectorId}`, {
    method: 'DELETE',
  });
}
