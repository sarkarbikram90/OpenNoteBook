/**
 * OpenNotebook — Toast notification store.
 *
 * Simple pub/sub for toast notifications.
 * React components subscribe via useToast hook.
 */

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
  duration?: number;
}

type ToastListener = (toasts: Toast[]) => void;

let toasts: Toast[] = [];
const listeners: Set<ToastListener> = new Set();
let idCounter = 0;

function notify(): void {
  listeners.forEach((listener) => listener([...toasts]));
}

export function subscribe(listener: ToastListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function addToast(
  type: ToastType,
  title: string,
  description?: string,
  duration = 5000,
): string {
  const id = `toast-${++idCounter}`;
  const toast: Toast = { id, type, title, description, duration };
  toasts = [...toasts, toast];
  notify();

  if (duration > 0) {
    setTimeout(() => removeToast(id), duration);
  }

  return id;
}

export function removeToast(id: string): void {
  toasts = toasts.filter((t) => t.id !== id);
  notify();
}

export function getToasts(): Toast[] {
  return [...toasts];
}
