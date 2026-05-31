/** OpenNotebook — Status badge component. */

import { clsx } from 'clsx';

interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 'processing';
  children: React.ReactNode;
  className?: string;
}

const variantStyles: Record<string, string> = {
  default:
    'bg-surface-700/50 text-surface-300 border-surface-600',
  success:
    'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  warning:
    'bg-amber-500/15 text-amber-400 border-amber-500/30',
  error:
    'bg-red-500/15 text-red-400 border-red-500/30',
  info:
    'bg-blue-500/15 text-blue-400 border-blue-500/30',
  processing:
    'bg-primary-500/15 text-primary-400 border-primary-500/30 animate-pulse-subtle',
};

export function Badge({ variant = 'default', children, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        variantStyles[variant],
        className,
      )}
    >
      {variant === 'processing' && (
        <span className="h-1.5 w-1.5 rounded-full bg-primary-400 animate-pulse" />
      )}
      {children}
    </span>
  );
}

/** Map source status to badge variant. */
export function statusBadgeVariant(
  status: string,
): BadgeProps['variant'] {
  switch (status) {
    case 'READY':
      return 'success';
    case 'FAILED':
      return 'error';
    case 'PENDING':
      return 'warning';
    case 'EXTRACTING':
    case 'CHUNKING':
    case 'EMBEDDING':
      return 'processing';
    default:
      return 'default';
  }
}
