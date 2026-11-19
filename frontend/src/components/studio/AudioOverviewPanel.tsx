/** OpenNotebook — Podcast-Style Audio Overview Studio Panel. */

import { useEffect, useRef, useState } from 'react';
import {
  Headphones,
  Sparkles,
  Play,
  Square,
  Download,
  Trash2,
  Loader2,
  Volume2,
  Mic,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import {
  useAudioOverviews,
  useCreateAudioOverview,
  useDeleteAudioOverview,
} from '@/hooks/useStudio';
import type { AudioOverview, AudioTone } from '@/lib/types';

interface AudioOverviewPanelProps {
  notebookId: string;
}

const TONE_OPTIONS: { value: AudioTone; label: string; desc: string }[] = [
  { value: 'deep_dive', label: 'Deep Dive', desc: 'In-depth two-host podcast exploration' },
  { value: 'brief', label: 'Executive Brief', desc: 'Crisp high-signal summary' },
  { value: 'debate', label: 'Critical Debate', desc: 'Pros, risks & counterarguments' },
];

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function AudioOverviewPanel({ notebookId }: AudioOverviewPanelProps) {
  const { data: overviews = [], isLoading } = useAudioOverviews(notebookId);
  const createMutation = useCreateAudioOverview(notebookId);
  const deleteMutation = useDeleteAudioOverview(notebookId);

  const [focusTopic, setFocusTopic] = useState('');
  const [tone, setTone] = useState<AudioTone>('deep_dive');
  const [selectedId, setSelectedId] = useState<string>('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [activeTurnIdx, setActiveTurnIdx] = useState<number>(-1);
  const [speechRate, setSpeechRate] = useState<number>(1.05);
  const cancelledRef = useRef(false);

  const activeOverview: AudioOverview | undefined =
    overviews.find((o) => o.id === selectedId) ?? overviews[0];

  const stopSpeech = () => {
    cancelledRef.current = true;
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
    setActiveTurnIdx(-1);
  };

  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const playWithWebSpeech = (overview: AudioOverview, startIndex = 0) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return;
    }
    window.speechSynthesis.cancel();
    cancelledRef.current = false;
    setIsSpeaking(true);

    const voices = window.speechSynthesis.getVoices();
    const enVoices = voices.filter((v) => v.lang.toLowerCase().startsWith('en'));
    const alexVoice = enVoices[0] ?? voices[0] ?? null;
    const samVoice = enVoices[1] ?? enVoices[0] ?? voices[0] ?? null;

    const speakTurn = (idx: number) => {
      if (cancelledRef.current || idx >= overview.turns.length) {
        setIsSpeaking(false);
        setActiveTurnIdx(-1);
        return;
      }
      const turn = overview.turns[idx];
      setActiveTurnIdx(idx);
      const utterance = new SpeechSynthesisUtterance(turn.text);
      utterance.rate = speechRate;
      utterance.pitch = turn.speaker.toLowerCase() === 'alex' ? 1.02 : 0.94;
      const chosenVoice =
        turn.speaker.toLowerCase() === 'alex' ? alexVoice : samVoice;
      if (chosenVoice) {
        utterance.voice = chosenVoice;
      }
      utterance.onend = () => speakTurn(idx + 1);
      utterance.onerror = () => {
        setIsSpeaking(false);
        setActiveTurnIdx(-1);
      };
      window.speechSynthesis.speak(utterance);
    };

    speakTurn(startIndex);
  };

  const handleGenerate = (e: React.FormEvent) => {
    e.preventDefault();
    stopSpeech();
    createMutation.mutate(
      { focus_topic: focusTopic.trim() || null, tone },
      {
        onSuccess: (created) => {
          setSelectedId(created.id);
          setFocusTopic('');
        },
      },
    );
  };

  const exportTranscript = (overview: AudioOverview) => {
    const lines = [
      `# ${overview.title}`,
      '',
      `> ${overview.summary}`,
      '',
      ...overview.turns.map((t) => `**${t.speaker}:** ${t.text}\n`),
    ].join('\n');
    const blob = new Blob([lines], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${overview.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left column: Generator + Episode History */}
      <aside className="w-80 shrink-0 border-r border-surface-700/30 bg-surface-900/40 flex flex-col overflow-y-auto p-4 space-y-6">
        <form onSubmit={handleGenerate} className="space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-surface-100">
            <Headphones className="h-4 w-4 text-primary-400" />
            Generate Audio Overview
          </div>

          <div>
            <label className="block text-xs font-medium text-surface-400 mb-1.5">
              Episode Style
            </label>
            <div className="space-y-1.5">
              {TONE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setTone(opt.value)}
                  className={`w-full text-left rounded-xl border px-3 py-2 transition-all ${
                    tone === opt.value
                      ? 'border-primary-500/60 bg-primary-500/15 text-surface-100'
                      : 'border-surface-700/40 bg-surface-900/50 text-surface-400 hover:border-surface-600'
                  }`}
                >
                  <p className="text-xs font-semibold">{opt.label}</p>
                  <p className="text-[11px] text-surface-500 mt-0.5">{opt.desc}</p>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-surface-400 mb-1">
              Focus Topic (optional)
            </label>
            <input
              type="text"
              value={focusTopic}
              onChange={(e) => setFocusTopic(e.target.value)}
              placeholder="e.g., latency benchmarks & trade-offs"
              className="w-full rounded-xl border border-surface-700/50 bg-surface-800/70 px-3 py-2 text-xs text-surface-100 focus:outline-none focus:border-primary-500"
            />
          </div>

          <button
            type="submit"
            disabled={createMutation.isPending}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-primary-500 transition-colors disabled:opacity-50"
          >
            {createMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Producing Episode...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Generate Two-Host Podcast
              </>
            )}
          </button>
        </form>

        {/* Episode History */}
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-surface-500">
            Episodes ({overviews.length})
          </p>
          {overviews.length === 0 ? (
            <p className="text-xs text-surface-500">
              No audio overviews generated yet.
            </p>
          ) : (
            <div className="space-y-1.5">
              {overviews.map((ep) => (
                <button
                  key={ep.id}
                  onClick={() => {
                    stopSpeech();
                    setSelectedId(ep.id);
                  }}
                  className={`w-full text-left rounded-xl border p-3 transition-all ${
                    activeOverview?.id === ep.id
                      ? 'border-primary-500/50 bg-primary-500/10'
                      : 'border-surface-700/30 bg-surface-900/40 hover:border-surface-600'
                  }`}
                >
                  <p className="text-xs font-semibold text-surface-100 truncate">
                    {ep.title}
                  </p>
                  <div className="flex items-center justify-between text-[10px] text-surface-500 mt-1">
                    <span>{ep.tone.replace('_', ' ')}</span>
                    <span>{formatDuration(ep.duration_seconds)}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Right column: Active Player + Synchronized Transcript */}
      <main className="flex-1 overflow-y-auto p-6">
        {!activeOverview ? (
          <div className="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto">
            <div className="h-14 w-14 rounded-2xl bg-primary-500/15 border border-primary-500/30 flex items-center justify-center mb-4">
              <Headphones className="h-7 w-7 text-primary-400" />
            </div>
            <h2 className="text-lg font-semibold text-surface-100">
              Notebook Audio Studio
            </h2>
            <p className="text-sm text-surface-500 mt-2">
              Turn your notebook sources into an engaging two-host podcast
              discussion between Alex and Sam—playable directly in-browser via
              dual-voice TTS or server-synthesized MP3.
            </p>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Player Header Card */}
            <div className="rounded-2xl border border-surface-700/40 bg-gradient-to-br from-surface-900 to-surface-900/60 p-6 space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <Badge variant="info">
                      {activeOverview.tone.replace('_', ' ')}
                    </Badge>
                    <Badge variant="default">
                      {activeOverview.source_count} source
                      {activeOverview.source_count === 1 ? '' : 's'}
                    </Badge>
                    <span className="text-xs text-surface-500 font-mono">
                      ~{formatDuration(activeOverview.duration_seconds)}
                    </span>
                  </div>
                  <h2 className="text-xl font-bold text-surface-100">
                    {activeOverview.title}
                  </h2>
                  {activeOverview.summary && (
                    <p className="text-sm text-surface-400 mt-1">
                      {activeOverview.summary}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => exportTranscript(activeOverview)}
                    className="rounded-lg p-2 text-surface-400 hover:text-surface-200 hover:bg-surface-800 transition-colors"
                    title="Download Markdown transcript"
                  >
                    <Download className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => {
                      stopSpeech();
                      deleteMutation.mutate(activeOverview.id);
                    }}
                    className="rounded-lg p-2 text-surface-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    title="Delete episode"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Native MP3 Audio Player if synthesized server-side */}
              {activeOverview.has_audio_file && activeOverview.audio_url && (
                <audio
                  controls
                  src={activeOverview.audio_url}
                  className="w-full h-10"
                />
              )}

              {/* Built-in Two-Host Web Speech Player */}
              <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-surface-700/30">
                {!isSpeaking ? (
                  <button
                    onClick={() => playWithWebSpeech(activeOverview, 0)}
                    className="flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-xs font-semibold text-white hover:bg-primary-500 transition-colors"
                  >
                    <Play className="h-3.5 w-3.5 fill-current" />
                    Play Two-Host Audio
                  </button>
                ) : (
                  <button
                    onClick={stopSpeech}
                    className="flex items-center gap-2 rounded-xl bg-red-600/80 px-4 py-2 text-xs font-semibold text-white hover:bg-red-500 transition-colors"
                  >
                    <Square className="h-3.5 w-3.5 fill-current" />
                    Stop Playback
                  </button>
                )}

                <label className="flex items-center gap-2 text-xs text-surface-400 ml-auto">
                  <Volume2 className="h-3.5 w-3.5" />
                  Speed
                  <select
                    aria-label="Playback speed"
                    value={speechRate}
                    onChange={(e) => setSpeechRate(parseFloat(e.target.value))}
                    className="rounded-lg border border-surface-700/50 bg-surface-800 px-2 py-1 text-xs text-surface-200"
                  >
                    <option value={0.9}>0.9x</option>
                    <option value={1.05}>1.0x</option>
                    <option value={1.25}>1.25x</option>
                    <option value={1.5}>1.5x</option>
                  </select>
                </label>
              </div>
            </div>

            {/* Interactive Synchronized Transcript */}
            <div className="space-y-2.5">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-surface-500">
                Interactive Transcript ({activeOverview.turns.length} turns)
              </h3>
              {activeOverview.turns.map((turn, idx) => {
                const isAlex = turn.speaker.toLowerCase() === 'alex';
                const isActive = idx === activeTurnIdx;
                return (
                  <button
                    key={idx}
                    onClick={() => playWithWebSpeech(activeOverview, idx)}
                    className={`w-full text-left rounded-2xl border p-4 transition-all ${
                      isActive
                        ? 'border-primary-500 bg-primary-500/15 shadow-lg shadow-primary-500/10'
                        : 'border-surface-700/30 bg-surface-900/50 hover:border-surface-600'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      <Mic
                        className={`h-3.5 w-3.5 ${
                          isAlex ? 'text-primary-400' : 'text-emerald-400'
                        }`}
                      />
                      <span
                        className={`text-xs font-bold ${
                          isAlex ? 'text-primary-300' : 'text-emerald-300'
                        }`}
                      >
                        {turn.speaker}
                      </span>
                      {isActive && (
                        <Badge variant="processing" className="ml-auto">
                          Speaking
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-surface-200 leading-relaxed">
                      {turn.text}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
