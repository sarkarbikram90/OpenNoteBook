/** OpenNotebook — Settings page: model registry, temperature, context window. */

import { useState, useEffect } from 'react';
import { Save, Loader2, Cpu, Thermometer, Layers, Hash, Zap } from 'lucide-react';
import { useSettings, useUpdateSettings } from '@/hooks/useSettings';
import { Spinner } from '@/components/ui/Spinner';
import type { SettingsUpdate } from '@/lib/types';

export function SettingsPage() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const [form, setForm] = useState<SettingsUpdate>({});

  // Sync form with fetched settings
  useEffect(() => {
    if (settings) {
      setForm({
        llm_model: settings.llm_model,
        embedding_model: settings.embedding_model,
        reranker_model: settings.reranker_model,
        llm_temperature: settings.llm_temperature,
        context_window: settings.context_window,
        max_chunks: settings.max_chunks,
      });
    }
  }, [settings]);

  const handleSave = () => {
    updateMutation.mutate(form);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-surface-100">Settings</h1>
          <p className="text-sm text-surface-500 mt-1">
            Configure your AI models and retrieval parameters.
          </p>
        </div>

        <div className="space-y-8">
          {/* Model Registry */}
          <Section title="Model Registry" icon={Cpu}>
            <SettingField
              label="LLM Model"
              description="Ollama model for text generation"
              value={form.llm_model ?? ''}
              onChange={(v) => setForm((f) => ({ ...f, llm_model: v }))}
              placeholder="llama3:8b-instruct"
            />
            <SettingField
              label="Embedding Model"
              description="Model for document embeddings"
              value={form.embedding_model ?? ''}
              onChange={(v) => setForm((f) => ({ ...f, embedding_model: v }))}
              placeholder="BAAI/bge-small-en-v1.5"
            />
            <SettingField
              label="Reranker Model"
              description="Cross-encoder for result reranking"
              value={form.reranker_model ?? ''}
              onChange={(v) => setForm((f) => ({ ...f, reranker_model: v }))}
              placeholder="BAAI/bge-reranker-base"
            />
          </Section>

          {/* Generation */}
          <Section title="Generation" icon={Zap}>
            <div>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <label className="text-sm font-medium text-surface-200 flex items-center gap-1.5">
                    <Thermometer className="h-3.5 w-3.5 text-surface-500" />
                    Temperature
                  </label>
                  <p className="text-xs text-surface-500 mt-0.5">
                    Lower = more focused, higher = more creative
                  </p>
                </div>
                <span className="text-sm font-mono text-primary-400 bg-primary-500/10 px-2 py-0.5 rounded-lg">
                  {Number(form.llm_temperature ?? 0.1).toFixed(1)}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={form.llm_temperature ?? 0.1}
                onChange={(e) =>
                  setForm((f) => ({ ...f, llm_temperature: parseFloat(e.target.value) }))
                }
                className="w-full h-2 rounded-full appearance-none bg-surface-700 accent-primary-500 cursor-pointer"
              />
              <div className="flex justify-between mt-1 text-[10px] text-surface-600">
                <span>Precise</span>
                <span>Creative</span>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-surface-200 flex items-center gap-1.5 mb-1.5">
                <Layers className="h-3.5 w-3.5 text-surface-500" />
                Context Window
              </label>
              <p className="text-xs text-surface-500 mb-2">
                Maximum token context for the LLM
              </p>
              <input
                type="number"
                min={512}
                max={131072}
                value={form.context_window ?? 8192}
                onChange={(e) =>
                  setForm((f) => ({ ...f, context_window: parseInt(e.target.value, 10) || 8192 }))
                }
                className="w-full rounded-xl border border-surface-700/40 bg-surface-800/60 px-4 py-2.5 text-sm text-surface-100 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
              />
            </div>
          </Section>

          {/* Retrieval */}
          <Section title="Retrieval" icon={Hash}>
            <div>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <label className="text-sm font-medium text-surface-200">
                    Max Retrieved Chunks
                  </label>
                  <p className="text-xs text-surface-500 mt-0.5">
                    Top-K chunks sent to LLM after reranking
                  </p>
                </div>
                <span className="text-sm font-mono text-primary-400 bg-primary-500/10 px-2 py-0.5 rounded-lg">
                  {form.max_chunks ?? 10}
                </span>
              </div>
              <input
                type="range"
                min="1"
                max="30"
                step="1"
                value={form.max_chunks ?? 10}
                onChange={(e) =>
                  setForm((f) => ({ ...f, max_chunks: parseInt(e.target.value, 10) }))
                }
                className="w-full h-2 rounded-full appearance-none bg-surface-700 accent-primary-500 cursor-pointer"
              />
              <div className="flex justify-between mt-1 text-[10px] text-surface-600">
                <span>1</span>
                <span>30</span>
              </div>
            </div>
          </Section>

          {/* Save */}
          <div className="flex justify-end pt-4 border-t border-surface-700/20">
            <button
              onClick={handleSave}
              disabled={updateMutation.isPending}
              className="flex items-center gap-2 rounded-xl bg-primary-600 px-6 py-2.5 text-sm font-medium text-white transition-all hover:bg-primary-500 disabled:opacity-50 shadow-lg shadow-primary-500/20"
            >
              {updateMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof Cpu;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-surface-700/30 bg-surface-800/20 p-6">
      <h2 className="text-base font-semibold text-surface-200 flex items-center gap-2 mb-5">
        <Icon className="h-5 w-5 text-primary-400" />
        {title}
      </h2>
      <div className="space-y-5">{children}</div>
    </div>
  );
}

function SettingField({
  label,
  description,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  description: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <div>
      <label className="text-sm font-medium text-surface-200 mb-1 block">{label}</label>
      <p className="text-xs text-surface-500 mb-2">{description}</p>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-xl border border-surface-700/40 bg-surface-800/60 px-4 py-2.5 text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
      />
    </div>
  );
}
