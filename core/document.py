"""Document — the top-level container for a parsed document."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from docstructure.core.analysis import DocumentAnalysis
from docstructure.core.common import Provenance
from docstructure.core.nodes import (
    BlockNode,
    Edge,
    GraphNode,
    ParagraphBlock,
    RegionNode,
    Run,
)


# ─────────────────────────────────────────────────────────────
# Document
# ─────────────────────────────────────────────────────────────


@dataclass
class Document:
    """A single parsed document. Mutable — stages modify it in place.

    The graph is the single source of truth:
      - nodes: all GraphNode instances (blocks + regions)
      - edges: semantic relationships between nodes

    Blocks and regions are convenience views derived from nodes.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    analysis: DocumentAnalysis = field(default_factory=DocumentAnalysis)

    ast_version: str = "docstructure/v1"
    parser: str = "docx"
    parser_version: str = "1.0"
    source: str = ""
    language: str = "unknown"
    language_confidence: float = 0.0

    # ── Internal bookkeeping ──
    _next_id: int = 1
    _node_map: dict[int, GraphNode] = field(default_factory=dict)

    # ── Convenience properties ──

    @property
    def blocks(self) -> list[BlockNode]:
        return [n for n in self.nodes if isinstance(n, BlockNode)]

    @property
    def regions(self) -> list[RegionNode]:
        return [n for n in self.nodes if isinstance(n, RegionNode)]

    @property
    def paragraphs(self) -> list[ParagraphBlock]:
        return [n for n in self.nodes if isinstance(n, ParagraphBlock)]

    # ── ID management ──

    def next_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def add_node(self, node: GraphNode) -> None:
        self.nodes.append(node)
        self._node_map[node.id] = node

    def get_node(self, nid: int) -> GraphNode | None:
        return self._node_map.get(nid)

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)

    # ── Query helpers ──

    def find(self, node_type: type, **attrs: Any) -> GraphNode | None:
        """Find first node matching type and optional attribute filters."""
        for n in self.nodes:
            if not isinstance(n, node_type):
                continue
            if all(getattr(n, k, None) == v for k, v in attrs.items()):
                return n
        return None

    def find_all(self, filter_fn: Callable[[GraphNode], bool]) -> list[GraphNode]:
        """Find all nodes matching a predicate."""
        return [n for n in self.nodes if filter_fn(n)]

    def walk(self) -> list[GraphNode]:
        """Depth-first traversal of all nodes."""
        return list(self.nodes)

    # ── Serialization ──
    # Use docstructure.output.json.serialize() for JSON output.
    # This method exists for quick debugging only.
