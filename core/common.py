"""Shared data types and enumerations for DocStructure."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ─────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────


class ParagraphRole(Enum):
    """Semantic role of a paragraph block."""
    BODY = "body"
    HEADING = "heading"
    CAPTION = "caption"
    REFERENCE = "reference"
    TOC_ENTRY = "toc_entry"
    ABSTRACT = "abstract"
    TITLE = "title"
    METADATA = "metadata"
    AUTHOR = "author"
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"
    APPENDIX = "appendix"


class RegionType(Enum):
    """Semantic region types (13 canonical types from architecture)."""
    TITLE_PAGE = "title_page"
    ABSTRACT = "abstract"
    TABLE_OF_CONTENTS = "table_of_contents"
    INTRODUCTION = "introduction"
    METHODOLOGY = "methodology"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"
    REFERENCES = "references"
    APPENDIX = "appendix"
    FRONT_MATTER = "front_matter"
    MAIN_CONTENT = "main_content"
    BACK_MATTER = "back_matter"


class EdgeType(Enum):
    """Types of semantic relationships between nodes."""
    HEADING_CONTAINS = "heading_contains"
    CITATION_REFERENCES = "citation_references"
    FIGURE_CAPTION = "figure_caption"
    FOOTNOTE_REF_TO = "footnote_ref_to"
    TOC_TARGETS = "toc_targets"


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


# ─────────────────────────────────────────────────────────────
# Provenance
# ─────────────────────────────────────────────────────────────


@dataclass
class Provenance:
    """Who created this fact, how confident, and why."""
    confidence: float = 0.0
    produced_by: str = ""
    version: str = "1.0"
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "produced_by": self.produced_by,
            "version": self.version,
            "evidence": self.evidence,
        }


# ─────────────────────────────────────────────────────────────
# Generic signal
# ─────────────────────────────────────────────────────────────


@dataclass
class Signal:
    """A single piece of evidence for a detection decision."""
    name: str
    score: int
