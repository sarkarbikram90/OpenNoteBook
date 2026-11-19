/** OpenNotebook — Workspaces, Governance & RBAC management page. */

import { useState } from 'react';
import {
  Users,
  ShieldCheck,
  Plus,
  UserPlus,
  Trash2,
  Loader2,
  Lock,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import {
  useAddWorkspaceMember,
  useCreateWorkspace,
  useRemoveWorkspaceMember,
  useUpdateWorkspace,
  useUpdateWorkspaceMemberRole,
  useWorkspaces,
  useWorkspaceMembers,
} from '@/hooks/useWorkspaces';
import type { SensitivityLevel, WorkspaceRole } from '@/lib/types';

const ROLES: WorkspaceRole[] = ['owner', 'admin', 'member', 'viewer'];
const SENSITIVITIES: SensitivityLevel[] = [
  'public',
  'internal',
  'confidential',
  'restricted',
];

export function WorkspacesPage() {
  const { data: workspaces = [], isLoading } = useWorkspaces();
  const [selectedId, setSelectedId] = useState<string>('');
  const activeWorkspace =
    workspaces.find((w) => w.id === selectedId) ?? workspaces[0];
  const activeWorkspaceId = activeWorkspace?.id ?? '';
  const canManage =
    activeWorkspace?.role === 'owner' || activeWorkspace?.role === 'admin';

  const { data: members = [], isLoading: membersLoading } = useWorkspaceMembers(
    activeWorkspaceId || undefined,
  );
  const createWsMutation = useCreateWorkspace();
  const updateWsMutation = useUpdateWorkspace();
  const addMemberMutation = useAddWorkspaceMember(activeWorkspaceId);
  const updateRoleMutation = useUpdateWorkspaceMemberRole(activeWorkspaceId);
  const removeMemberMutation = useRemoveWorkspaceMember(activeWorkspaceId);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newWsName, setNewWsName] = useState('');
  const [newWsPii, setNewWsPii] = useState(true);
  const [newWsSensitivity, setNewWsSensitivity] =
    useState<SensitivityLevel>('internal');

  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<WorkspaceRole>('member');

  const handleCreateWorkspace = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    createWsMutation.mutate(
      {
        name: newWsName.trim(),
        enable_pii_redaction: newWsPii,
        default_sensitivity: newWsSensitivity,
      },
      {
        onSuccess: (created) => {
          setSelectedId(created.id);
          setNewWsName('');
          setIsCreateOpen(false);
        },
      },
    );
  };

  const handleInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    addMemberMutation.mutate(
      { email: inviteEmail.trim(), role: inviteRole },
      {
        onSuccess: () => {
          setInviteEmail('');
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto h-full">
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-surface-100 flex items-center gap-2.5">
              <Users className="h-6 w-6 text-primary-400" />
              Workspaces & Access Control
            </h1>
            <p className="text-sm text-surface-500 mt-1">
              Manage team workspaces, role-based permissions, PII redaction, and
              data sensitivity policies.
            </p>
          </div>

          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Workspace
          </button>
        </div>

        {/* Workspace selector cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {workspaces.map((ws) => {
            const isSelected = ws.id === activeWorkspace?.id;
            return (
              <button
                key={ws.id}
                onClick={() => setSelectedId(ws.id)}
                className={`text-left rounded-2xl border p-4 transition-all ${
                  isSelected
                    ? 'border-primary-500/60 bg-primary-500/10'
                    : 'border-surface-700/40 bg-surface-900/50 hover:border-surface-600'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-surface-100 truncate">
                    {ws.name}
                  </span>
                  <Badge variant={ws.role === 'owner' ? 'info' : 'default'}>
                    {ws.role}
                  </Badge>
                </div>
                <p className="text-xs text-surface-500 mt-2">
                  {ws.member_count} member{ws.member_count === 1 ? '' : 's'} ·{' '}
                  {ws.default_sensitivity}
                </p>
              </button>
            );
          })}
        </div>

        {activeWorkspace && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Governance Policy Panel */}
            <section className="rounded-2xl border border-surface-700/40 bg-surface-900/60 p-5 space-y-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-surface-200">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                Governance Policy
              </div>

              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-surface-200">
                    Automated PII Redaction
                  </p>
                  <p className="text-xs text-surface-500 mt-0.5">
                    Scrub SSNs, emails, and cards via Rust DFA / Presidio during
                    ingestion.
                  </p>
                </div>
                <input
                  type="checkbox"
                  aria-label="Enable PII redaction"
                  checked={activeWorkspace.enable_pii_redaction}
                  disabled={!canManage || updateWsMutation.isPending}
                  onChange={(e) =>
                    updateWsMutation.mutate({
                      id: activeWorkspace.id,
                      data: { enable_pii_redaction: e.target.checked },
                    })
                  }
                  className="h-4 w-4 accent-primary-500 cursor-pointer"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-surface-300 flex items-center gap-1.5 mb-1.5">
                  <Lock className="h-3.5 w-3.5 text-surface-500" />
                  Default Data Sensitivity
                </label>
                <select
                  aria-label="Default sensitivity level"
                  value={activeWorkspace.default_sensitivity}
                  disabled={!canManage || updateWsMutation.isPending}
                  onChange={(e) =>
                    updateWsMutation.mutate({
                      id: activeWorkspace.id,
                      data: {
                        default_sensitivity: e.target.value as SensitivityLevel,
                      },
                    })
                  }
                  className="w-full rounded-xl border border-surface-700/50 bg-surface-800/70 px-3 py-2 text-sm text-surface-100 focus:outline-none focus:border-primary-500 disabled:opacity-50"
                >
                  {SENSITIVITIES.map((s) => (
                    <option key={s} value={s}>
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
            </section>

            {/* Members & RBAC Panel */}
            <section className="lg:col-span-2 rounded-2xl border border-surface-700/40 bg-surface-900/60 p-5 space-y-5">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-surface-200">
                  Workspace Members & RBAC ({members.length})
                </h2>
              </div>

              {canManage && (
                <form
                  onSubmit={handleInvite}
                  className="flex flex-wrap items-center gap-2"
                >
                  <input
                    type="email"
                    required
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="colleague@company.com"
                    className="flex-1 min-w-[200px] rounded-xl border border-surface-700/50 bg-surface-800/70 px-3 py-2 text-sm text-surface-100 focus:outline-none focus:border-primary-500"
                  />
                  <select
                    aria-label="Invite member role"
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as WorkspaceRole)}
                    className="rounded-xl border border-surface-700/50 bg-surface-800/70 px-3 py-2 text-sm text-surface-100 focus:outline-none focus:border-primary-500"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                  <button
                    type="submit"
                    disabled={addMemberMutation.isPending}
                    className="flex items-center gap-1.5 rounded-xl bg-primary-600 px-3.5 py-2 text-sm font-semibold text-white hover:bg-primary-500 transition-colors disabled:opacity-50"
                  >
                    {addMemberMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <UserPlus className="h-4 w-4" />
                    )}
                    Add Member
                  </button>
                </form>
              )}

              {membersLoading ? (
                <div className="flex justify-center py-6">
                  <Spinner />
                </div>
              ) : (
                <div className="divide-y divide-surface-800">
                  {members.map((m) => (
                    <div
                      key={m.user_id}
                      className="flex items-center justify-between gap-3 py-3"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-surface-100 truncate">
                          {m.email}
                        </p>
                        <p className="text-[11px] text-surface-500">
                          Joined {new Date(m.created_at).toLocaleDateString()}
                        </p>
                      </div>

                      <div className="flex items-center gap-2">
                        <select
                          aria-label={`Role for ${m.email}`}
                          value={m.role}
                          disabled={!canManage || updateRoleMutation.isPending}
                          onChange={(e) =>
                            updateRoleMutation.mutate({
                              userId: m.user_id,
                              role: e.target.value as WorkspaceRole,
                            })
                          }
                          className="rounded-lg border border-surface-700/50 bg-surface-800/70 px-2.5 py-1 text-xs text-surface-200 focus:outline-none focus:border-primary-500 disabled:opacity-50"
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>

                        {canManage && (
                          <button
                            onClick={() => removeMemberMutation.mutate(m.user_id)}
                            disabled={removeMemberMutation.isPending}
                            className="rounded-lg p-1.5 text-surface-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                            title="Remove member"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>

      {/* Create Workspace Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create Workspace"
        size="sm"
      >
        <form onSubmit={handleCreateWorkspace} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-surface-300 mb-1">
              Workspace Name
            </label>
            <input
              type="text"
              required
              value={newWsName}
              onChange={(e) => setNewWsName(e.target.value)}
              placeholder="Platform Engineering"
              className="w-full rounded-xl border border-surface-700/50 bg-surface-800/70 px-3 py-2 text-sm text-surface-100 focus:outline-none focus:border-primary-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-surface-300 mb-1">
              Default Sensitivity
            </label>
            <select
              value={newWsSensitivity}
              onChange={(e) =>
                setNewWsSensitivity(e.target.value as SensitivityLevel)
              }
              className="w-full rounded-xl border border-surface-700/50 bg-surface-800/70 px-3 py-2 text-sm text-surface-100 focus:outline-none focus:border-primary-500"
            >
              {SENSITIVITIES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <label className="flex items-center gap-2 text-sm text-surface-300 cursor-pointer">
            <input
              type="checkbox"
              checked={newWsPii}
              onChange={(e) => setNewWsPii(e.target.checked)}
              className="h-4 w-4 accent-primary-500"
            />
            Enable automated PII redaction
          </label>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsCreateOpen(false)}
              className="rounded-xl px-4 py-2 text-sm text-surface-400 hover:bg-surface-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createWsMutation.isPending}
              className="flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:opacity-50"
            >
              {createWsMutation.isPending && (
                <Loader2 className="h-4 w-4 animate-spin" />
              )}
              Create
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
