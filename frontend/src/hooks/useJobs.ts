/** OpenNotebook — TanStack Query hooks for Failed Jobs / DLQ. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { listFailedJobs, retryFailedJob } from '@/lib/api/jobs';
import { addToast } from '@/stores/toast';

export function useFailedJobs() {
  return useQuery({
    queryKey: ['failed-jobs'],
    queryFn: listFailedJobs,
    refetchInterval: 30_000,
  });
}

export function useRetryJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => retryFailedJob(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['failed-jobs'] });
      addToast('success', 'Job re-queued', 'Ingestion task has been dispatched for retry');
    },
    onError: (err: Error) => {
      addToast('error', 'Retry failed', err.message);
    },
  });
}
