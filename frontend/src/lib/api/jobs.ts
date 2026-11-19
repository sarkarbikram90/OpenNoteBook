/** OpenNotebook — Failed Jobs / DLQ API client. */

import { apiFetch } from '@/lib/api';
import type { FailedJobListResponse, RetryJobResponse } from '@/lib/types';

export function listFailedJobs(): Promise<FailedJobListResponse> {
  return apiFetch<FailedJobListResponse>('/jobs/failed');
}

export function retryFailedJob(jobId: string): Promise<RetryJobResponse> {
  return apiFetch<RetryJobResponse>(`/jobs/${jobId}/retry`, {
    method: 'POST',
  });
}
