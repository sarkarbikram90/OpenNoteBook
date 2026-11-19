/** Vitest tests for ConnectorsPage and WorkspacesPage. */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConnectorsPage } from './ConnectorsPage';
import { WorkspacesPage } from './WorkspacesPage';

vi.mock('@/hooks/useWorkspaces', () => ({
  useWorkspaces: () => ({
    isLoading: false,
    data: [
      {
        id: 'ws-1',
        organization_id: 'org-1',
        name: 'Engineering Workspace',
        slug: 'engineering',
        role: 'owner',
        enable_pii_redaction: true,
        default_sensitivity: 'internal',
        member_count: 2,
        created_at: '2026-11-01T00:00:00Z',
        updated_at: '2026-11-01T00:00:00Z',
      },
    ],
  }),
  useWorkspaceMembers: () => ({
    isLoading: false,
    data: [
      {
        user_id: 'u-1',
        email: 'owner@example.com',
        role: 'owner',
        created_at: '2026-11-01T00:00:00Z',
      },
    ],
  }),
  useCreateWorkspace: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateWorkspace: () => ({ mutate: vi.fn(), isPending: false }),
  useAddWorkspaceMember: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateWorkspaceMemberRole: () => ({ mutate: vi.fn(), isPending: false }),
  useRemoveWorkspaceMember: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('@/hooks/useNotebook', () => ({
  useNotebooks: () => ({
    data: [{ id: 'nb-1', name: 'Architecture Docs' }],
  }),
}));

vi.mock('@/hooks/useConnectors', () => ({
  useConnectors: () => ({
    isLoading: false,
    data: [
      {
        id: 'conn-1',
        workspace_id: 'ws-1',
        notebook_id: 'nb-1',
        name: 'Eng Confluence',
        connector_type: 'confluence',
        schedule_cron: '0 */6 * * *',
        status: 'ACTIVE',
        last_sync_at: null,
        error_message: null,
      },
    ],
  }),
  useCreateConnector: () => ({ mutate: vi.fn(), isPending: false }),
  useTestConnector: () => ({ mutate: vi.fn(), isPending: false }),
  useSyncConnector: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteConnector: () => ({ mutate: vi.fn(), isPending: false }),
}));

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('Enterprise Frontend Parity Pages', () => {
  it('renders ConnectorsPage with configured connector and catalog', () => {
    renderWithQuery(<ConnectorsPage />);
    expect(screen.getByText('Enterprise Connectors')).toBeInTheDocument();
    expect(screen.getByText('Eng Confluence')).toBeInTheDocument();
    expect(screen.getByText('SharePoint')).toBeInTheDocument();
    expect(screen.getByText('Salesforce')).toBeInTheDocument();
  });

  it('renders WorkspacesPage with governance policy and RBAC members', () => {
    renderWithQuery(<WorkspacesPage />);
    expect(screen.getByText('Workspaces & Access Control')).toBeInTheDocument();
    expect(screen.getByText('Engineering Workspace')).toBeInTheDocument();
    expect(screen.getByText('Automated PII Redaction')).toBeInTheDocument();
    expect(screen.getByText('owner@example.com')).toBeInTheDocument();
  });
});
