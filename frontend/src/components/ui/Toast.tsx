/** OpenNotebook — Toast notification component. */

import { useState, useEffect } from 'react';
import { clsx } from 'clsx';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { subscribe, removeToast, getToasts, type Toast as ToastType } from '@/stores/toast';

const iconMap = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const colorMap = {
  success: 'border-emerald-500/40 bg-emerald-500/10',
  error: 'border-red-500/40 bg-red-500/10',
  warning: 'border-amber-500/40 bg-amber-500/10',
  info: 'border-blue-500/40 bg-blue-500/10',
};

const iconColorMap = {
  success: 'text-emerald-400',
  error: 'text-red-400',
  warning: 'text-amber-400',
  info: 'text-blue-400',
};

function ToastItem({ toast }: { toast: ToastType }) {
  const Icon = iconMap[toast.type];

  return (
    <div
      className={clsx(
        'flex items-start gap-3 rounded-xl border p-4 shadow-lg shadow-black/20 backdrop-blur-sm animate-slide-up',
        colorMap[toast.type],
      )}
      role="alert"
    >
      <Icon className={clsx('h-5 w-5 mt-0.5 shrink-0', iconColorMap[toast.type])} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-surface-100">{toast.title}</p>
        {toast.description && (
          <p className="mt-1 text-xs text-surface-400">{toast.description}</p>
        )}
      </div>
      <button
        onClick={() => removeToast(toast.id)}
        className="shrink-0 rounded-lg p-1 text-surface-500 transition-colors hover:text-surface-300"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastType[]>(() => getToasts());

  useEffect(() => {
    return subscribe(setToasts);
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 w-80">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
