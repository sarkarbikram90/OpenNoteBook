/** Vitest tests for AudioOverviewPanel and KnowledgeGraphPanel. */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AudioOverviewPanel } from './AudioOverviewPanel';
import { KnowledgeGraphPanel } from './KnowledgeGraphPanel';

vi.mock('@/hooks/useStudio', () => ({
  useAudioOverviews: () => ({
    isLoading: false,
    data: [
      {
        id: 'ao-1',
        notebook_id: 'nb-1',
        title: 'Rust Core Deep Dive',
        summary: 'Alex and Sam unpack PyO3 acceleration benchmarks.',
        focus_topic: 'Rust performance',
        tone: 'deep_dive',
        status: 'READY',
        turns: [
          { speaker: 'Alex', text: 'Welcome to OpenNotebook Audio Studio!' },
          { speaker: 'Sam', text: 'Today we examine the 34.2x BM25 speedup.' },
        ],
        duration_seconds: 95,
        source_count: 2,
        has_audio_file: false,
        audio_url: null,
        playback_mode: 'browser_tts',
        created_at: '2026-11-19T00:00:00Z',
      },
    ],
  }),
  useCreateAudioOverview: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteAudioOverview: () => ({ mutate: vi.fn(), isPending: false }),
  useKnowledgeGraph: () => ({
    isLoading: false,
    data: {
      notebook_id: 'nb-1',
      nodes: [
        { id: 'source:s1', label: 'rust-accel.pdf', kind: 'source', weight: 4, source_ids: ['s1'] },
        { id: 'concept:pyo3', label: 'PyO3', kind: 'concept', weight: 3, source_ids: ['s1'] },
        { id: 'organization:opennotebook', label: 'OpenNotebook', kind: 'organization', weight: 5, source_ids: ['s1'] },
      ],
      edges: [
        { source: 'source:s1', target: 'concept:pyo3', relation: 'MENTIONS', weight: 3 },
        { source: 'concept:pyo3', target: 'organization:opennotebook', relation: 'CO_OCCURS', weight: 2 },
      ],
      matched_node_ids: ['concept:pyo3'],
      stats: { total_nodes: 3, total_edges: 2, sources: 1, entities: 2 },
    },
  }),
}));

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('Studio Multimodal Panels', () => {
  it('renders AudioOverviewPanel with episode player and dialogue transcript', () => {
    renderWithQuery(<AudioOverviewPanel notebookId="nb-1" />);
    expect(screen.getAllByText('Rust Core Deep Dive').length).toBeGreaterThan(0);
    expect(screen.getByText('Welcome to OpenNotebook Audio Studio!')).toBeInTheDocument();
    expect(screen.getByText('Play Two-Host Audio')).toBeInTheDocument();
  });

  it('renders KnowledgeGraphPanel with interactive SVG nodes and stats', () => {
    renderWithQuery(<KnowledgeGraphPanel notebookId="nb-1" />);
    expect(screen.getByLabelText('Interactive Notebook Knowledge Graph')).toBeInTheDocument();
    expect(screen.getByText('3 nodes')).toBeInTheDocument();
    expect(screen.getByText('2 edges')).toBeInTheDocument();
    expect(screen.getByText('PyO3')).toBeInTheDocument();
  });
});
