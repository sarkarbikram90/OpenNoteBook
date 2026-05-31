/** OpenNotebook — Landing page with hero and feature highlights. */

import { BookOpen, Shield, Zap, Search, ArrowRight } from 'lucide-react';

interface LandingPageProps {
  onGetStarted: () => void;
}

export function LandingPage({ onGetStarted }: LandingPageProps) {
  return (
    <div className="min-h-screen bg-surface-950 flex flex-col">
      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-20 text-center">
        {/* Logo */}
        <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-2xl shadow-primary-500/30 mb-8 animate-fade-in">
          <BookOpen className="h-10 w-10 text-white" />
        </div>

        <h1 className="text-5xl font-extrabold tracking-tight text-surface-100 mb-4 animate-fade-in max-w-3xl">
          Your private, open-source{' '}
          <span className="bg-gradient-to-r from-primary-400 to-violet-400 bg-clip-text text-transparent">
            AI research assistant
          </span>
        </h1>

        <p className="text-lg text-surface-400 max-w-2xl mb-10 animate-fade-in">
          Understand anything. Keep everything local. Upload documents, ask questions,
          and get grounded answers with inline citations — all powered by local AI models.
        </p>

        <button
          onClick={onGetStarted}
          className="flex items-center gap-2 rounded-2xl bg-gradient-to-r from-primary-600 to-primary-500 px-8 py-4 text-base font-semibold text-white shadow-xl shadow-primary-500/30 transition-all hover:shadow-2xl hover:shadow-primary-500/40 hover:scale-[1.02] active:scale-[0.98] animate-fade-in"
        >
          Get Started
          <ArrowRight className="h-5 w-5" />
        </button>
      </div>

      {/* Features */}
      <div className="border-t border-surface-800 bg-surface-900/40 px-6 py-16">
        <div className="max-w-5xl mx-auto grid grid-cols-1 gap-8 md:grid-cols-3">
          <FeatureCard
            icon={Shield}
            title="100% Private"
            description="All AI inference runs locally. No data ever leaves your machine. No API keys needed."
          />
          <FeatureCard
            icon={Search}
            title="Grounded Citations"
            description="Every answer is backed by inline citations with source, page, and relevance scores."
          />
          <FeatureCard
            icon={Zap}
            title="Real-Time Streaming"
            description="Token-by-token streaming responses via SSE. See answers form as the AI thinks."
          />
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-surface-800 py-6 text-center text-xs text-surface-600">
        OpenNotebook — Open source under Apache 2.0
      </footer>
    </div>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof BookOpen;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-surface-700/20 bg-surface-800/30 p-6 transition-all hover:border-surface-700/50 hover:bg-surface-800/50">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-600/15 mb-4">
        <Icon className="h-5 w-5 text-primary-400" />
      </div>
      <h3 className="text-base font-semibold text-surface-200 mb-2">{title}</h3>
      <p className="text-sm text-surface-400 leading-relaxed">{description}</p>
    </div>
  );
}
