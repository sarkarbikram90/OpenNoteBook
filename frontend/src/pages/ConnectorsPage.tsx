/** OpenNotebook — Enterprise Connectors management page. */

import { useState } from 'react';
import {
  Plug,
  Plus,
  RefreshCw,
  CheckCircle2,
  Trash2,
  Loader2,
  Database,
  Globe,
  Cloud,
  FolderOpen,
  FileCode2,
  Building2,
  Clock,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { useWorkspaces } from '@/hooks/useWorkspaces';
import { useNotebooks } from '@/hooks/useNotebook';
import {
  useConnectors,
  useCreateConnector,
  useDeleteConnector,
  useSyncConnector,
  useTestConnector,
} from '@/hooks/useConnectors';
import type { ConnectorType } from '@/lib/types';

interface ConnectorTemplate {
  type: ConnectorType;
  label: string;
  description: string;
  defaultConfig: Record<string, unknown>;
}

const CONNECTOR_TEMPLATES: ConnectorTemplate[] = [
  {
    type: 'confluence',
    label: 'Confluence',
    description: 'Sync wiki spaces and pages with space-level ACLs.',
    defaultConfig: {
      base_url: 'https://your-org.atlassian.net/wiki',
      space_key: 'ENG',
      email: 'bot@company.com',
      api_token: '',
    },
  },
  {
    type: 'sharepoint',
    label: 'SharePoint',
    description: 'Ingest Microsoft 365 document libraries via Graph API.',
    defaultConfig: {
      tenant_id: '',
      client_id: '',
      client_secret: '',
      site_id: '',
    },
  },
  {
    type: 'salesforce',
    label: 'Salesforce',
    description: 'Index Knowledge articles, Cases, and CRM notes.',
    defaultConfig: {
      instance_url: 'https://your-org.my.salesforce.com',
      access_token: '',
      soql_query: 'SELECT Id, Title, Summary FROM Knowledge__kav',
    },
  },
  {
    type: 's3',
    label: 'Amazon S3',
    description: 'Continuously ingest documents from an S3 bucket prefix.',
    defaultConfig: {
      bucket: 'my-enterprise-docs',
      prefix: 'knowledge/',
      region: 'us-east-1',
    },
  },
  {
    type: 'sql',
    label: 'SQL Database',
    description: 'Sync structured rows as searchable documents via SQL.',
    defaultConfig: {
      connection_url: 'postgresql://readonly:pass@host:5432/db',
      query: 'SELECT id, title, body FROM articles',
    },
  },
  {
    type: 'web',
    label: 'Web Crawler',
    description: 'Fetch and clean documentation URLs with trafilatura.',
    defaultConfig: {
      urls: ['https://docs.example.com'],
    },
  },
  {
    type: 'fileshare',
    label: 'Local Fileshare',
    description: 'Index mounted network drives or local directories.',
    defaultConfig: {
      root_path: '/mnt/shared-docs',
      extensions: ['.pdf', '.md', '.txt', '.docx'],
    },
  },
  {
    type: 'rest',
    label: 'Generic REST API',
    description: 'Pull JSON collections from any authenticated REST endpoint.',
    defaultConfig: {
      url: 'https://api.example.com/v1/documents',
      headers: { Authorization: 'Bearer YOUR_TOKEN' },
    },
  },
];

function connectorIcon(type: ConnectorType) {
  switch (type) {
    case 'sql':
      return <Database className="h-4 w-4 text-primary-400" />;
    case 'web':
      return <Globe className="h-4 w-4 text-blue-400" />;
    case 's3':
      return <Cloud className="h-4 w-4 text-amber-400" />;
    case 'fileshare':
      return <FolderOpen className="h-4 w-4 text-emerald-400" />;
    case 'rest':
      return <FileCode2 className="h-4 w-4 text-purple-400" />;
    default:
      return <Building2 className="h-4 w-4 text-primary-400" />;
  }
}

export function ConnectorsPage() {
  const { data: workspaces = [], isLoading: wsLoading } = useWorkspaces();
  const { data: notebooks = [] } = useNotebooks();

  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>('');
  const activeWorkspaceId = selectedWorkspaceId || workspaces[0]?.id || '';
  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId);
  const canManage =
    activeWorkspace?.role === 'owner' || activeWorkspace?.role === 'admin';

  const { data: connectors = [], isLoading: connLoading } = useConnectors(
    activeWorkspaceId || undefined,
  );
  const createMutation = useCreateConnector(activeWorkspaceId);
  const testMutation = useTestConnector();
  const syncMutation = useSyncConnector(activeWorkspaceId);
  const deleteMutation = useDeleteConnector(activeWorkspaceId);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [connectorType, setConnectorType] = useState<ConnectorType>('confluence');
  const [notebookId, setNotebookId] = useState<string>('');
  const [scheduleCron, setScheduleCron] = useState('');
  const [configText, setConfigText] = useState(() =>
    JSON.stringify(CONNECTOR_TEMPLATES[0].defaultConfig, null, 2),
  );
  const [configError, setConfigError] = useState<string | null>(null);

  const openModalWithType = (type: ConnectorType) => {
    const template =
      CONNECTOR_TEMPLATES.find((t) => t.type === type) ?? CONNECTOR_TEMPLATES[0];
    setConnectorType(template.type);
    setName(`${template.label} Sync`);
    setNotebookId(notebooks[0]?.id ?? '');
    setScheduleCron('');
    setConfigText(JSON.stringify(template.defaultConfig, null, 2));
    setConfigError(null);
    setIsModalOpen(true);
  };

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspaceId || !name.trim()) return;

    let parsedConfig: Record<string, unknown>;
    try {
      parsedConfig = JSON.parse(configText || '{}');
      setConfigError(null);
    } catch {
      setConfigError('Configuration must be valid JSON.');
      return;
    }

    createMutation.mutate(
      {
        workspace_id: activeWorkspaceId,
        notebook_id: notebookId || null,
        name: name.trim(),
        connector_type: connectorType,
        config_json: parsedConfig,
        schedule_cron: scheduleCron.trim() || null,
      },
      {
        onSuccess: () => {
          setIsModalOpen(false);
        },
      },
    );
  };

  if (wsLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto h-full">
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-surface-100 flex items-center gap-2.5">
              <Plug className="h-6 w-6 text-primary-400" />
              Enterprise Connectors
            </h1>
            <p className="text-sm text-surface-500 mt-1">
              Ingest and incrementally sync knowledge from Confluence, SharePoint,
              Salesforce, S3, SQL, and REST APIs with ACL propagation.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {workspaces.length > 0 && (
              <select
                aria-label="Select workspace"
                value={activeWorkspaceId}
                onChange={(e) => setSelectedWorkspaceId(e.target.value)}
                className="rounded-xl border border-surface-700/50 bg-surface-900 px-3 py-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
              >
                {workspaces.map((ws) => (
                  <option key={ws.id} value={ws.id}>
                    {ws.name} ({ws.role})
                  </option>
                ))}
              </select>
            )}

            <button
              onClick={() => openModalWithType('confluence')}
              disabled={!canManage}
              className="flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 transition-colors disabled:opacity-40"
            >
              <Plus className="h-4 w-4" />
              Add Connector
            </button>
          </div>
        </div>

        {/* Active Connectors */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-surface-400">
              Configured Connectors ({connectors.length})
            </h2>
          </div>

          {connLoading ? (
            <div className="flex justify-center py-12">
              <Spinner />
            </div>
          ) : connectors.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-surface-700/50 bg-surface-900/30 p-10 text-center">
              <Plug className="h-8 w-8 text-surface-600 mx-auto mb-3" />
              <p className="text-sm font-medium text-surface-300">
                No connectors configured in this workspace yet
              </p>
              <p className="text-xs text-surface-500 mt-1">
                Pick a connector template below to wire an external knowledge source into a
                notebook.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {connectors.map((conn) => {
                const targetNb = notebooks.find((n) => n.id === conn.notebook_id);
                return (
                  <div
                    key={conn.id}
                    className="rounded-2xl border border-surface-700/40 bg-surface-900/60 p-5 flex flex-col justify-between gap-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface-800 border border-surface-700/40">
                          {connectorIcon(conn.connector_type)}
                        </div>
                        <div className="min-w-0">
                          <h3 className="text-sm font-semibold text-surface-100 truncate">
                            {conn.name}
                          </h3>
                          <p className="text-xs text-surface-500 uppercase tracking-wide mt-0.5">
                            {conn.connector_type}
                            {targetNb ? ` · → ${targetNb.name}` : ' · No target notebook'}
                          </p>
                        </div>
                      </div>
                      <Badge
                        variant={
                          conn.status === 'ACTIVE'
                            ? 'success'
                            : conn.status === 'ERROR'
                              ? 'error'
                              : 'warning'
                        }
                      >
                        {conn.status}
                      </Badge>
                    </div>

                    <div className="text-xs text-surface-400 space-y-1">
                      <div className="flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-surface-500" />
                        <span>
                          Last sync:{' '}
                          {conn.last_sync_at
                            ? new Date(conn.last_sync_at).toLocaleString()
                            : 'Never'}
                        </span>
                      </div>
                      {conn.schedule_cron && (
                        <p className="font-mono text-[11px] text-surface-500">
                          Schedule: {conn.schedule_cron}
                        </p>
                      )}
                      {conn.error_message && (
                        <p className="text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-2.5 py-1.5 mt-1">
                          {conn.error_message}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-2 pt-2 border-t border-surface-700/30">
                      <button
                        onClick={() => testMutation.mutate(conn.id)}
                        disabled={!canManage || testMutation.isPending}
                        className="flex items-center gap-1.5 rounded-lg border border-surface-700/50 bg-surface-800/60 px-3 py-1.5 text-xs font-medium text-surface-200 hover:bg-surface-800 transition-colors disabled:opacity-40"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                        Test
                      </button>
                      <button
                        onClick={() => syncMutation.mutate(conn.id)}
                        disabled={!canManage || !conn.notebook_id || syncMutation.isPending}
                        className="flex items-center gap-1.5 rounded-lg bg-primary-600/20 border border-primary-500/30 px-3 py-1.5 text-xs font-medium text-primary-300 hover:bg-primary-600/30 transition-colors disabled:opacity-40"
                      >
                        {syncMutation.isPending ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3.5 w-3.5" />
                        )}
                        Sync Now
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(conn.id)}
                        disabled={!canManage || deleteMutation.isPending}
                        className="ml-auto rounded-lg p-1.5 text-surface-500 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40"
                        title="Delete connector"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Connector Catalog */}
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-surface-400">
            Available Integrations
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {CONNECTOR_TEMPLATES.map((tpl) => (
              <button
                key={tpl.type}
                onClick={() => openModalWithType(tpl.type)}
                disabled={!canManage}
                className="text-left rounded-xl border border-surface-700/30 bg-surface-900/40 p-4 hover:border-primary-500/40 hover:bg-surface-900/80 transition-all disabled:opacity-40"
              >
                <div className="flex items-center gap-2.5 mb-2">
                  {connectorIcon(tpl.type)}
                  <span className="text-sm font-semibold text-surface-100">
                    {tpl.label}
                  </span>
                </div>
                <p className="text-xs text-surface-500 leading-relaxed">
                  {tpl.description}
                </p>
              </button>
            ))}
          </div>
        </section>
      </div>

      {/* Create Connector Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Configure Enterprise Connector"
        size="lg"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-surface-300 mb-1">
                Connector Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Engineering Confluence"
                className="w-full rounded-xl border border-surface-700/50 bg-surface-800/70 px-3 py-2 text-sm text-surface-100 focus:outline-none focus:border-primary-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-surface-300 mb-1">
                Connector Type
              </label>
              <select
                value={connectorType}
                onChange={(e) => {
                  const next = e.target.value as ConnectorType;
                  setConnectorType(next);
                  const tpl = CONNECTOR_TEMPLATES.find((t) => t.type === next);
                  if (tpl) {
                    setConfigText(JSON.stringify(tpl.defaultConfig, null, 2));
                  }
                }}
                className="w-full rounded-xl border border-surface-700/50 bg-surface-800/70 px-3 py-2 text-sm text-surface-100 focus:outline-none focus:border-primary-500"
              >
                {CONNECTOR_TEMPLATES.map((t) => (
                  <option key={t.type} value={t.type}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-surface-300 mb-1">
                Target Notebook
              </label>
              <select
                value={notebookId}
                onChange={(e) => setNotebookId(e.target.value)}
                className="w-full rounded-xl border border-surface-700/50 bg-surface-800/70 px-3 py-2 text-sm text-surface-100 focus:outline-none focus:border-primary-500"
              >
                <option value="">— Select notebook —</option>
                {notebooks.map((nb) => (
                  <option key={nb.id} value={nb.id}>
                    {nb.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-surface-300 mb-1">
                Sync Schedule (Cron, optional)
              </label>
              <input
                type="text"
                value={scheduleCron}
                onChange={(e) => setScheduleCron(e.target.value)}
                placeholder="0 */6 * * *"
                className="w-full rounded-xl border border-surface-700/50 bg-surface-800/70 px-3 py-2 text-sm font-mono text-surface-100 focus:outline-none focus:border-primary-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-surface-300 mb-1">
              Connector Configuration (JSON)
            </label>
            <textarea
              rows={7}
              value={configText}
              onChange={(e) => setConfigText(e.target.value)}
              className="w-full rounded-xl border border-surface-700/50 bg-surface-950/80 px-3 py-2 text-xs font-mono text-surface-200 focus:outline-none focus:border-primary-500"
            />
            {configError && (
              <p className="text-xs text-red-400 mt-1">{configError}</p>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="rounded-xl px-4 py-2 text-sm text-surface-400 hover:bg-surface-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 transition-colors disabled:opacity-50"
            >
              {createMutation.isPending && (
                <Loader2 className="h-4 w-4 animate-spin" />
              )}
              Save Connector
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
