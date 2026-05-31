/** OpenNotebook — Real-time processing progress indicator (SSE-driven). */

import { clsx } from 'clsx';
import { Check, Loader2, AlertCircle } from 'lucide-react';
import type { SourceStatus } from '@/lib/types';

interface ProcessingProgressProps {
  status: SourceStatus;
  className?: string;
}

const steps: { status: SourceStatus; label: string }[] = [
  { status: 'PENDING', label: 'Queued' },
  { status: 'EXTRACTING', label: 'Extracting' },
  { status: 'CHUNKING', label: 'Chunking' },
  { status: 'EMBEDDING', label: 'Embedding' },
  { status: 'READY', label: 'Ready' },
];

const statusOrder: Record<string, number> = {
  PENDING: 0,
  EXTRACTING: 1,
  CHUNKING: 2,
  EMBEDDING: 3,
  READY: 4,
  FAILED: -1,
};

export function ProcessingProgress({ status, className }: ProcessingProgressProps) {
  const currentIdx = statusOrder[status] ?? 0;
  const isFailed = status === 'FAILED';

  if (isFailed) {
    return (
      <div className={clsx('flex items-center gap-2 text-red-400', className)}>
        <AlertCircle className="h-4 w-4" />
        <span className="text-xs font-medium">Processing failed</span>
      </div>
    );
  }

  if (status === 'READY') {
    return (
      <div className={clsx('flex items-center gap-2 text-emerald-400', className)}>
        <Check className="h-4 w-4" />
        <span className="text-xs font-medium">Ready</span>
      </div>
    );
  }

  return (
    <div className={clsx('space-y-2', className)}>
      {/* Progress bar */}
      <div className="h-1.5 w-full rounded-full bg-surface-700/50 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-primary-500 to-primary-400 transition-all duration-500 ease-out"
          style={{ width: `${((currentIdx + 0.5) / (steps.length - 1)) * 100}%` }}
        />
      </div>

      {/* Step indicators */}
      <div className="flex justify-between">
        {steps.map((step, i) => {
          const isComplete = i < currentIdx;
          const isCurrent = i === currentIdx;

          return (
            <div key={step.status} className="flex flex-col items-center">
              <div
                className={clsx(
                  'flex h-5 w-5 items-center justify-center rounded-full text-xs transition-all',
                  isComplete && 'bg-primary-500 text-white',
                  isCurrent && 'bg-primary-500/20 text-primary-400 border border-primary-500/50',
                  !isComplete && !isCurrent && 'bg-surface-700/50 text-surface-500',
                )}
              >
                {isComplete ? (
                  <Check className="h-3 w-3" />
                ) : isCurrent ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <span className="text-[10px]">{i + 1}</span>
                )}
              </div>
              <span
                className={clsx(
                  'mt-1 text-[10px]',
                  isCurrent ? 'text-primary-400 font-medium' : 'text-surface-500',
                )}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
