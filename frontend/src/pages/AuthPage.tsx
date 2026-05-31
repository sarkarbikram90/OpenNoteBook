/** OpenNotebook — Auth page with login/register tabs. */

import { useState, type FormEvent } from 'react';
import { clsx } from 'clsx';
import { BookOpen, Loader2, ArrowLeft } from 'lucide-react';
import { useLogin, useRegister } from '@/hooks/useAuth';

interface AuthPageProps {
  onSuccess: () => void;
  onBack: () => void;
}

type Tab = 'login' | 'register';

export function AuthPage({ onSuccess, onBack }: AuthPageProps) {
  const [tab, setTab] = useState<Tab>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const loginMutation = useLogin();
  const registerMutation = useRegister();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const mutation = tab === 'login' ? loginMutation : registerMutation;
    mutation.mutate(
      { email, password },
      { onSuccess },
    );
  };

  const isPending = loginMutation.isPending || registerMutation.isPending;

  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Back button */}
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-sm text-surface-500 hover:text-surface-300 transition-colors mb-8"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>

        {/* Logo */}
        <div className="flex items-center gap-3 mb-8">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-lg shadow-primary-500/20">
            <BookOpen className="h-5 w-5 text-white" />
          </div>
          <div>
            <p className="text-lg font-bold text-surface-100">OpenNotebook</p>
            <p className="text-xs text-surface-500">AI Research Assistant</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-xl bg-surface-800/60 p-1 mb-6">
          {(['login', 'register'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={clsx(
                'flex-1 rounded-lg py-2 text-sm font-medium transition-all capitalize',
                tab === t
                  ? 'bg-primary-600 text-white shadow-md'
                  : 'text-surface-400 hover:text-surface-200',
              )}
            >
              {t === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="auth-email" className="block text-sm text-surface-300 mb-1.5">
              Email
            </label>
            <input
              id="auth-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              placeholder="you@example.com"
              className="w-full rounded-xl border border-surface-700/40 bg-surface-800/60 px-4 py-2.5 text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
            />
          </div>

          <div>
            <label htmlFor="auth-password" className="block text-sm text-surface-300 mb-1.5">
              Password
            </label>
            <input
              id="auth-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              placeholder="••••••••"
              className="w-full rounded-xl border border-surface-700/40 bg-surface-800/60 px-4 py-2.5 text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
            />
          </div>

          <button
            type="submit"
            disabled={isPending}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary-600 py-3 text-sm font-medium text-white transition-all hover:bg-primary-500 disabled:opacity-50 shadow-lg shadow-primary-500/20"
          >
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : tab === 'login' ? (
              'Sign In'
            ) : (
              'Create Account'
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
