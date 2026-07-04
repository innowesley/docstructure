"""JSON output — serialize Document to JSON matching schema v2."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from docstructure.core.analysis import Diagnostic, DocumentAnalysis, Location, ReferenceEntry
from docstructure.core.common import ParagraphRole, Provenance, RegionType, Severity, Signal
from docstructure.core.document import Document
from docstructure.core.nodes import (
    BlockFeatures,
    BlockNode,
    CodeBlock,
    Edge,
    EquationBlock,
    FigureBlock,
    GraphNode,
    ListBlock,
    ListItem,
    PageBreak,
    ParagraphBlock,
    RegionNode,
    Run,
    SectionBreak,
    TableBlock,
    TableCell,
    TableRow,
)


_NODE_KIND_MAP = {
    ParagraphBlock: "paragraph",
    TableBlock: "table",
    ListBlock: "list",
    FigureBlock: "figure",
    CodeBlock: "code",
    EquationBlock: "equation",
    RegionNode: "region",
    PageBreak: "page_break",
    SectionBreak: "section_break",
}


def _node_kind(node: GraphNode) -> str:
    for cls, kind in _NODE_KIND_MAP.items():
        if isinstance(node, cls):
            return kind
    return "unknown"


def _serialize(obj: Any) -> Any:
    """Recursively serialize dataclasses and non-serializable types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, type):
        return obj.__name__
    if is_dataclass(obj):
        return {k: _serialize(v) for k, v in asdict(obj).items() if v is not None}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (int, float, str, bool)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if obj is None:
        return None
    return str(obj)


def _build_sections(doc: Document) -> list[dict]:
    sections = []
    for region in doc.regions:
        region_dict = _serialize(region)
        section = {
            "id": region.id,
            "type": region.region_type.value if isinstance(region.region_type, RegionType) else str(region.region_type),
            "label": region_dict.get("label", ""),
            "level": 0,
            "block_ids": region_dict.get("block_ids", []),
            "confidence": region.provenance.confidence if region.provenance else 1.0,
        }
        sections.append(section)
    return sections


def _build_diagnostics(doc: Document) -> list[dict]:
    if not doc.analysis:
        return []
    diags = []
    for d in doc.analysis.diagnostics:
        diags.append({
            "rule": d.rule_name if hasattr(d, 'rule_name') else d.rule_id,
            "severity": d.severity.value if isinstance(d.severity, Severity) else str(d.severity),
            "message": d.message,
            "location": _serialize(d.location) if d.location else None,
        })
    return diags


def _build_references(doc: Document) -> list[dict]:
    if not doc.analysis or not doc.analysis.references:
        return []
    return [_serialize(ref) for ref in doc.analysis.references]


_SCHEMA_URLS = {
    "v1": "https://raw.githubusercontent.com/innowesley/docstructure/main/output/schema/v1.json",
    "v2": "https://raw.githubusercontent.com/innowesley/docstructure/main/output/schema/v2.json",
}


def serialize(doc: Document, schema_version: str = "v2", debug: bool = False) -> dict:
    """Serialize document to schema-compatible dict.

    Outputs v2 schema by default (superset of v1). Use schema_version="v1"
    for v1 compatibility. Adds format_detection and validation blocks
    when available for v2. Pass debug=True to include full classification
    scores and metadata in output.
    """
    nodes_out = []
    for node in doc.nodes:
        node_dict = _serialize(node)
        kind = _node_kind(node)
        entry = {
            "id": node.id,
            "kind": kind,
            **node_dict,
        }
        if isinstance(node, ParagraphBlock) and node.role:
            entry["role"] = node.role.value if isinstance(node.role, ParagraphRole) else str(node.role)
        if isinstance(node, ParagraphBlock) and node.heading_level:
            entry["heading_level"] = node.heading_level
        if isinstance(node, ParagraphBlock) and node.classification:
            cl = node.classification
            cls_entry = {
                "label": cl.label.value,
                "confidence": cl.confidence,
                "classifier": {
                    "name": cl.classifier.name,
                    "version": cl.classifier.version,
                },
            }
            if debug:
                if cl.scores:
                    cls_entry["scores"] = dict(cl.scores)
                if cl.metadata:
                    cls_entry["metadata"] = dict(cl.metadata)
            entry["classification"] = cls_entry
        nodes_out.append(entry)

    schema_url = _SCHEMA_URLS.get(schema_version, _SCHEMA_URLS["v2"])
    output: dict = {
        "schema": schema_url,
        "document": {
            "id": doc.id,
            "source": doc.source,
            "parser": doc.parser,
            "parser_version": doc.parser_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "source": doc.source or "",
                "file_format": "docx",
                "page_count": None,
                "char_count": sum(len(b.text) for b in doc.paragraphs),
            },
        },
        "nodes": nodes_out,
        "edges": _serialize(doc.edges),
        "sections": _build_sections(doc),
        "diagnostics": _build_diagnostics(doc),
        "references": _build_references(doc),
    }

    # Add format detection (v2 addition; omit for v1)
    if schema_version == "v2" and doc.analysis and doc.analysis.format_detection is not None:
        output["format_detection"] = doc.analysis.format_detection.to_dict()

    # Add validation results (v2 addition; omit for v1)
    if schema_version == "v2" and doc.analysis and doc.analysis.validation is not None:
        output["validation"] = doc.analysis.validation.to_dict()

    return output


def to_json(doc: Document, indent: int = 2, schema_version: str = "v2", debug: bool = False) -> str:
    """Serialize document to JSON string."""
    return json.dumps(serialize(doc, schema_version=schema_version, debug=debug), indent=indent)


def to_file(doc: Document, path: str, indent: int = 2, schema_version: str = "v2", debug: bool = False) -> None:
    """Write document JSON to a file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_json(doc, indent=indent, schema_version=schema_version, debug=debug))
