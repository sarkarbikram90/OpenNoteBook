/** OpenNotebook — Interactive Knowledge Graph & GraphRAG Explorer Panel. */

import { useMemo, useState } from 'react';
import { Network, Search, FileText, Sparkles, X } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { useKnowledgeGraph } from '@/hooks/useStudio';
import type { GraphNode, GraphNodeKind } from '@/lib/types';

interface KnowledgeGraphPanelProps {
  notebookId: string;
}

const KIND_COLORS: Record<GraphNodeKind, string> = {
  source: '#38bdf8',       // sky-400
  concept: '#a78bfa',      // violet-400
  organization: '#34d399', // emerald-400
  person: '#fbbf24',       // amber-400
};

const KIND_LABELS: Record<GraphNodeKind, string> = {
  source: 'Sources',
  concept: 'Concepts',
  organization: 'Organizations',
  person: 'People',
};

interface PositionedNode extends GraphNode {
  x: number;
  y: number;
  r: number;
}

export function KnowledgeGraphPanel({ notebookId }: KnowledgeGraphPanelProps) {
  const [searchInput, setSearchInput] = useState('');
  const [activeQuery, setActiveQuery] = useState('');
  const [kindFilter, setKindFilter] = useState<GraphNodeKind | 'all'>('all');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const { data: graph, isLoading } = useKnowledgeGraph(
    notebookId,
    activeQuery || undefined,
  );

  const matchedSet = useMemo(
    () => new Set(graph?.matched_node_ids ?? []),
    [graph?.matched_node_ids],
  );

  // Deterministic concentric radial layout (sources in inner ring, entities in outer ring)
  const { positionedNodes, nodeById, visibleEdges } = useMemo(() => {
    const rawNodes = graph?.nodes ?? [];
    const filtered =
      kindFilter === 'all'
        ? rawNodes
        : rawNodes.filter((n) => n.kind === kindFilter || n.kind === 'source');

    const sources = filtered.filter((n) => n.kind === 'source');
    const entities = filtered.filter((n) => n.kind !== 'source');

    const cx = 420;
    const cy = 270;
    const positioned: PositionedNode[] = [];

    sources.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(1, sources.length) - Math.PI / 2;
      const radius = sources.length <= 1 ? 0 : 95;
      positioned.push({
        ...node,
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
        r: Math.min(24, 14 + Math.sqrt(node.weight) * 2.5),
      });
    });

    entities.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(1, entities.length) - Math.PI / 2;
      const ringOffset = i % 2 === 0 ? 205 : 240;
      positioned.push({
        ...node,
        x: cx + Math.cos(angle) * ringOffset,
        y: cy + Math.sin(angle) * (ringOffset * 0.85),
        r: Math.min(20, 8 + Math.sqrt(node.weight) * 2.4),
      });
    });

    const map = new Map<string, PositionedNode>();
    positioned.forEach((n) => map.set(n.id, n));

    const edges = (graph?.edges ?? []).filter(
      (e) => map.has(e.source) && map.has(e.target),
    );

    return { positionedNodes: positioned, nodeById: map, visibleEdges: edges };
  }, [graph, kindFilter]);

  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) ?? null : null;

  const connectedNeighbors = useMemo(() => {
    if (!selectedNode) return [];
    const neighbors: { node: PositionedNode; relation: string; weight: number }[] = [];
    for (const e of visibleEdges) {
      if (e.source === selectedNode.id) {
        const target = nodeById.get(e.target);
        if (target) neighbors.push({ node: target, relation: e.relation, weight: e.weight });
      } else if (e.target === selectedNode.id) {
        const source = nodeById.get(e.source);
        if (source) neighbors.push({ node: source, relation: e.relation, weight: e.weight });
      }
    }
    return neighbors.sort((a, b) => b.weight - a.weight);
  }, [selectedNode, visibleEdges, nodeById]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setActiveQuery(searchInput.trim());
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 border-b border-surface-700/30 bg-surface-900/50 px-5 py-3">
        <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1 min-w-[240px] max-w-md">
          <div className="relative flex-1">
            <Search className="h-3.5 w-3.5 text-surface-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="GraphRAG traversal query (e.g., pgvector, latency)..."
              className="w-full rounded-xl border border-surface-700/50 bg-surface-800/70 pl-9 pr-8 py-1.5 text-xs text-surface-100 focus:outline-none focus:border-primary-500"
            />
            {activeQuery && (
              <button
                type="button"
                onClick={() => {
                  setSearchInput('');
                  setActiveQuery('');
                }}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-200"
                aria-label="Clear GraphRAG query"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          <button
            type="submit"
            className="flex items-center gap-1.5 rounded-xl bg-primary-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary-500"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Traverse
          </button>
        </form>

        {/* Kind Filter Pills */}
        <div className="flex items-center gap-1.5">
          {(['all', 'source', 'concept', 'organization', 'person'] as const).map(
            (kind) => (
              <button
                key={kind}
                onClick={() => setKindFilter(kind)}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                  kindFilter === kind
                    ? 'bg-primary-600/25 text-primary-300 border border-primary-500/40'
                    : 'text-surface-400 hover:text-surface-200 border border-transparent'
                }`}
              >
                {kind === 'all' ? 'All' : KIND_LABELS[kind]}
              </button>
            ),
          )}
        </div>

        {/* Stats */}
        {graph && (
          <div className="ml-auto flex items-center gap-2 text-xs text-surface-400">
            <Badge variant="default">{graph.stats.total_nodes} nodes</Badge>
            <Badge variant="default">{graph.stats.total_edges} edges</Badge>
            {activeQuery && (
              <Badge variant="info">{matchedSet.size} matched</Badge>
            )}
          </div>
        )}
      </div>

      {/* Main Canvas + Inspector */}
      <div className="flex-1 flex overflow-hidden">
        {positionedNodes.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
            <Network className="h-10 w-10 text-surface-600 mb-3" />
            <p className="text-sm font-semibold text-surface-200">
              No knowledge graph entities yet
            </p>
            <p className="text-xs text-surface-500 mt-1 max-w-sm">
              Upload documents to this notebook to automatically extract
              entities, concepts, and cross-document relationships.
            </p>
          </div>
        ) : (
          <div className="flex-1 relative overflow-hidden bg-surface-950/60">
            <svg
              viewBox="0 0 840 540"
              className="w-full h-full select-none"
              role="img"
              aria-label="Interactive Notebook Knowledge Graph"
            >
              {/* Edges */}
              {visibleEdges.map((edge, idx) => {
                const src = nodeById.get(edge.source);
                const tgt = nodeById.get(edge.target);
                if (!src || !tgt) return null;

                const isHighlighted =
                  selectedNodeId === edge.source ||
                  selectedNodeId === edge.target ||
                  (matchedSet.size > 0 &&
                    matchedSet.has(edge.source) &&
                    matchedSet.has(edge.target));

                return (
                  <line
                    key={`${edge.source}-${edge.target}-${idx}`}
                    x1={src.x}
                    y1={src.y}
                    x2={tgt.x}
                    y2={tgt.y}
                    stroke={isHighlighted ? '#818cf8' : '#334155'}
                    strokeWidth={isHighlighted ? 2 : 1}
                    strokeOpacity={
                      matchedSet.size > 0 && !isHighlighted ? 0.18 : 0.6
                    }
                    strokeDasharray={
                      edge.relation === 'CO_OCCURS' ? '4 3' : undefined
                    }
                  />
                );
              })}

              {/* Nodes */}
              {positionedNodes.map((node) => {
                const color = KIND_COLORS[node.kind] ?? '#94a3b8';
                const isSelected = node.id === selectedNodeId;
                const isMatched = matchedSet.has(node.id);
                const dimmed = matchedSet.size > 0 && !isMatched && !isSelected;

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x}, ${node.y})`}
                    onClick={() => setSelectedNodeId(node.id)}
                    className="cursor-pointer"
                    opacity={dimmed ? 0.25 : 1}
                  >
                    {(isSelected || isMatched) && (
                      <circle
                        r={node.r + 5}
                        fill="none"
                        stroke={color}
                        strokeWidth={2}
                        strokeOpacity={0.75}
                      />
                    )}
                    <circle
                      r={node.r}
                      fill={color}
                      fillOpacity={node.kind === 'source' ? 0.9 : 0.78}
                      stroke="#0f172a"
                      strokeWidth={2}
                    />
                    <text
                      y={node.r + 13}
                      textAnchor="middle"
                      fill="#e2e8f0"
                      fontSize={node.kind === 'source' ? 11 : 10}
                      fontWeight={node.kind === 'source' ? 600 : 400}
                    >
                      {node.label.length > 22
                        ? `${node.label.slice(0, 20)}…`
                        : node.label}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* Legend */}
            <div className="absolute bottom-4 left-4 flex items-center gap-3 rounded-xl border border-surface-700/40 bg-surface-900/90 px-3 py-2 text-[11px] text-surface-300 backdrop-blur">
              {(Object.keys(KIND_COLORS) as GraphNodeKind[]).map((kind) => (
                <span key={kind} className="flex items-center gap-1.5">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: KIND_COLORS[kind] }}
                  />
                  {KIND_LABELS[kind]}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Side Node Inspector */}
        {selectedNode && (
          <aside className="w-72 shrink-0 border-l border-surface-700/30 bg-surface-900/60 p-4 overflow-y-auto space-y-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <Badge variant="info">{selectedNode.kind}</Badge>
                <h3 className="text-sm font-bold text-surface-100 mt-1.5 break-words">
                  {selectedNode.label}
                </h3>
              </div>
              <button
                onClick={() => setSelectedNodeId(null)}
                className="rounded-lg p-1 text-surface-500 hover:text-surface-200 hover:bg-surface-800"
                aria-label="Close inspector"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="text-xs text-surface-400 space-y-1">
              <p>Connectivity weight: {selectedNode.weight}</p>
              <p>Linked sources: {selectedNode.source_ids.length}</p>
            </div>

            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-surface-500">
                Connected Nodes ({connectedNeighbors.length})
              </p>
              {connectedNeighbors.map(({ node, relation }) => (
                <button
                  key={`${node.id}-${relation}`}
                  onClick={() => setSelectedNodeId(node.id)}
                  className="w-full text-left rounded-xl border border-surface-700/30 bg-surface-800/40 px-3 py-2 hover:border-primary-500/40 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <FileText className="h-3.5 w-3.5 text-surface-400 shrink-0" />
                    <span className="text-xs font-medium text-surface-200 truncate">
                      {node.label}
                    </span>
                  </div>
                  <p className="text-[10px] text-surface-500 mt-0.5">
                    {relation} · {node.kind}
                  </p>
                </button>
              ))}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
