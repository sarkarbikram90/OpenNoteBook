/** OpenNotebook — Ingestion Jobs & Dead-Letter Queue (DLQ) dashboard. */

import { Activity, RotateCcw, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { useFailedJobs, useRetryJob } from '@/hooks/useJobs';

export function JobsPage() {
  const { data, isLoading, refetch, isFetching } = useFailedJobs();
  const retryMutation = useRetryJob();
  const jobs = data?.jobs ?? [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto h-full">
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-surface-100 flex items-center gap-2.5">
              <Activity className="h-6 w-6 text-primary-400" />
              Ingestion Jobs & Dead-Letter Queue
            </h1>
            <p className="text-sm text-surface-500 mt-1">
              Inspect failed document extraction or embedding tasks and replay
              them directly to the ingestion worker.
            </p>
          </div>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 rounded-xl border border-surface-700/50 bg-surface-900 px-3.5 py-2 text-sm text-surface-200 hover:bg-surface-800 transition-colors"
          >
            {isFetching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RotateCcw className="h-4 w-4" />
            )}
            Refresh
          </button>
        </div>

        {jobs.length === 0 ? (
          <div className="rounded-2xl border border-surface-700/40 bg-surface-900/40 p-12 text-center">
            <CheckCircle2 className="h-9 w-9 text-emerald-400 mx-auto mb-3" />
            <p className="text-base font-semibold text-surface-100">
              All ingestion pipelines healthy
            </p>
            <p className="text-xs text-surface-500 mt-1">
              There are currently zero failed jobs in the dead-letter queue.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="rounded-2xl border border-surface-700/40 bg-surface-900/60 p-5 space-y-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5 min-w-0">
                    <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-surface-100 font-mono">
                        {job.task_name}
                      </p>
                      <p className="text-xs text-surface-500 mt-0.5">
                        Source ID: <span className="font-mono">{job.source_id}</span> ·
                        Retries: {job.retry_count} ·{' '}
                        {new Date(job.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Badge variant={job.retried ? 'info' : 'error'}>
                      {job.retried ? 'Retried' : 'Failed'}
                    </Badge>
                    <button
                      onClick={() => retryMutation.mutate(job.id)}
                      disabled={job.retried || retryMutation.isPending}
                      className="flex items-center gap-1.5 rounded-lg bg-primary-600/20 border border-primary-500/30 px-3 py-1.5 text-xs font-medium text-primary-300 hover:bg-primary-600/30 transition-colors disabled:opacity-40"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      Retry
                    </button>
                  </div>
                </div>

                <p className="text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2 font-mono break-words">
                  {job.error_message}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
