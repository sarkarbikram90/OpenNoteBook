"""OpenNotebook — Interactive Knowledge Graph & GraphRAG Traversal Engine.

Constructs a notebook entity-relationship graph from:
1. Structured entities extracted in ``SourceSummary.entities`` (people, organisations, concepts).
2. Deterministic concept/entity extraction over ``DocumentChunk`` text so newly
   uploaded notebooks immediately display rich cross-document relationships.

Also provides k-hop GraphRAG neighborhood traversal for query-focused exploration.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

_STOPWORDS = frozenset(
    {
        "the", "and", "for", "that", "this", "with", "from", "have", "were", "been",
        "their", "there", "which", "about", "would", "could", "should", "into", "over",
        "after", "before", "between", "through", "during", "without", "within", "using",
        "based", "also", "more", "most", "some", "such", "than", "then", "when", "where",
        "while", "what", "will", "your", "they", "them", "these", "those", "each", "other",
        "first", "second", "third", "section", "page", "figure", "table", "document",
        "introduction", "conclusion", "summary", "overview", "chapter", "note", "notes",
        "january", "february", "march", "april", "may", "june", "july", "august",
        "september", "october", "november", "december", "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday",
    }
)

_CAPITALIZED_PHRASE_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9\-]+(?:\s+[A-Z][A-Za-z0-9\-]+){0,2})\b"
)


@dataclass
class GraphNode:
    """Node in the notebook knowledge graph."""

    id: str
    label: str
    kind: str  # "source" | "person" | "organization" | "concept"
    weight: int
    source_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "weight": self.weight,
            "source_ids": self.source_ids,
        }


@dataclass
class GraphEdge:
    """Weighted relationship edge between two knowledge graph nodes."""

    source: str
    target: str
    relation: str  # "MENTIONS" | "CO_OCCURS"
    weight: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight,
        }


@dataclass
class KnowledgeGraphResult:
    """Complete notebook knowledge graph with optional GraphRAG match highlights."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    matched_node_ids: list[str]
    stats: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "matched_node_ids": self.matched_node_ids,
            "stats": self.stats,
        }


def _canonical_entity_id(kind: str, label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return f"{kind}:{slug}"


def extract_phrases_from_text(text: str, *, max_terms: int = 12) -> list[str]:
    """Extract salient multi-word capitalized concepts/entities from chunk text."""
    counts: Counter[str] = Counter()
    for match in _CAPITALIZED_PHRASE_RE.finditer(text):
        phrase = match.group(1).strip()
        lower = phrase.lower()
        if len(phrase) < 3 or lower in _STOPWORDS:
            continue
        words = phrase.split()
        if all(w.lower() in _STOPWORDS for w in words):
            continue
        counts[phrase] += 1

    return [term for term, _ in counts.most_common(max_terms)]


def build_notebook_knowledge_graph(
    sources: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    *,
    query: str | None = None,
    max_entities: int = 36,
) -> KnowledgeGraphResult:
    """Build a connected Knowledge Graph from notebook sources, summaries, and chunks.

    Args:
        sources: List of dicts with ``id`` and ``name``.
        summaries: List of dicts with ``source_id`` and ``entities`` (people/organisations/concepts).
        chunks: List of dicts with ``source_id`` and ``text``.
        query: Optional GraphRAG search query to compute 1-hop matched neighborhood.
        max_entities: Maximum non-source entity nodes to retain (ranked by mention frequency).
    """
    source_nodes: dict[str, GraphNode] = {}
    for src in sources:
        sid = str(src["id"])
        source_nodes[f"source:{sid}"] = GraphNode(
            id=f"source:{sid}",
            label=str(src["name"]),
            kind="source",
            weight=1,
            source_ids=[sid],
        )

    entity_counts: Counter[str] = Counter()
    entity_meta: dict[str, tuple[str, str]] = {}  # entity_id -> (label, kind)
    entity_sources: dict[str, set[str]] = defaultdict(set)
    co_occurrence: Counter[tuple[str, str]] = Counter()

    def _record_entity(source_id: str, label: str, kind: str, boost: int = 1) -> str | None:
        clean = label.strip()
        if len(clean) < 2 or clean.lower() in _STOPWORDS:
            return None
        eid = _canonical_entity_id(kind, clean)
        entity_counts[eid] += boost
        entity_meta.setdefault(eid, (clean, kind))
        entity_sources[eid].add(source_id)
        return eid

    # 1. Structured entities from SourceSummary
    kind_map = {
        "people": "person",
        "organisations": "organization",
        "organizations": "organization",
        "concepts": "concept",
    }
    for summary in summaries:
        sid = str(summary.get("source_id") or "")
        entities = summary.get("entities") or {}
        if not isinstance(entities, dict):
            continue
        doc_eids: list[str] = []
        for raw_key, node_kind in kind_map.items():
            values = entities.get(raw_key) or []
            if not isinstance(values, list):
                continue
            for val in values:
                eid = _record_entity(sid, str(val), node_kind, boost=3)
                if eid:
                    doc_eids.append(eid)
        unique_eids = sorted(set(doc_eids))
        for i in range(len(unique_eids)):
            for j in range(i + 1, min(len(unique_eids), i + 8)):
                co_occurrence[(unique_eids[i], unique_eids[j])] += 2

    # 2. Salient concepts from DocumentChunk texts (with chunk-level co-occurrence)
    for chunk in chunks[:250]:
        sid = str(chunk.get("source_id") or "")
        text = str(chunk.get("text") or "")
        phrases = extract_phrases_from_text(text, max_terms=8)
        chunk_eids: list[str] = []
        for phrase in phrases:
            # Prefer existing person/organization node if label matches
            existing_match = None
            for existing_kind in ("person", "organization"):
                candidate = _canonical_entity_id(existing_kind, phrase)
                if candidate in entity_meta:
                    existing_match = candidate
                    break
            if existing_match:
                entity_counts[existing_match] += 1
                entity_sources[existing_match].add(sid)
                chunk_eids.append(existing_match)
            else:
                eid = _record_entity(sid, phrase, "concept", boost=1)
                if eid:
                    chunk_eids.append(eid)
        unique_chunk_eids = sorted(set(chunk_eids))
        for i in range(len(unique_chunk_eids)):
            for j in range(i + 1, min(len(unique_chunk_eids), i + 6)):
                co_occurrence[(unique_chunk_eids[i], unique_chunk_eids[j])] += 1

    # Select top entities by salience
    top_entity_ids = [eid for eid, _ in entity_counts.most_common(max_entities)]
    top_entity_set = set(top_entity_ids)

    nodes: list[GraphNode] = list(source_nodes.values())
    for eid in top_entity_ids:
        label, kind = entity_meta[eid]
        nodes.append(
            GraphNode(
                id=eid,
                label=label,
                kind=kind,
                weight=int(entity_counts[eid]),
                source_ids=sorted(entity_sources[eid]),
            )
        )

    edges: list[GraphEdge] = []
    # Source -> Entity MENTIONS edges
    for eid in top_entity_ids:
        for sid in sorted(entity_sources[eid]):
            src_node_id = f"source:{sid}"
            if src_node_id in source_nodes:
                edges.append(
                    GraphEdge(
                        source=src_node_id,
                        target=eid,
                        relation="MENTIONS",
                        weight=max(1, entity_counts[eid]),
                    )
                )
                source_nodes[src_node_id].weight += 1

    # Entity <-> Entity CO_OCCURS edges
    for (u, v), weight in co_occurrence.most_common(80):
        if u in top_entity_set and v in top_entity_set and weight >= 1:
            edges.append(
                GraphEdge(
                    source=u,
                    target=v,
                    relation="CO_OCCURS",
                    weight=int(weight),
                )
            )

    matched_ids = traverse_neighborhood(nodes, edges, query=query) if query else []

    stats = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "sources": len(source_nodes),
        "entities": len(top_entity_ids),
    }
    return KnowledgeGraphResult(
        nodes=nodes,
        edges=edges,
        matched_node_ids=matched_ids,
        stats=stats,
    )


def traverse_neighborhood(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    *,
    query: str | None,
    hops: int = 1,
) -> list[str]:
    """GraphRAG k-hop neighborhood traversal starting from query-matching nodes."""
    if not query or not query.strip():
        return []

    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", query) if len(t) >= 2]
    if not tokens:
        return []

    seeds: set[str] = set()
    for node in nodes:
        lower_label = node.label.lower()
        if any(tok in lower_label for tok in tokens):
            seeds.add(node.id)

    if not seeds:
        return []

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.source].add(edge.target)
        adjacency[edge.target].add(edge.source)

    visited = set(seeds)
    frontier = set(seeds)
    for _ in range(hops):
        next_frontier: set[str] = set()
        for nid in frontier:
            for neighbor in adjacency.get(nid, ()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
        frontier = next_frontier
        if not frontier:
            break

    return sorted(visited)
