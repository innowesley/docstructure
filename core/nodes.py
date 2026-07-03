"""GraphNode hierarchy — all typed nodes in the document graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from docstructure.core.common import ParagraphRole, Provenance, RegionType


# ─────────────────────────────────────────────────────────────
# Base node
# ─────────────────────────────────────────────────────────────


@dataclass
class GraphNode:
    """Every node in the document graph inherits from this."""
    id: int
    provenance: Provenance = field(default_factory=Provenance)


# ─────────────────────────────────────────────────────────────
# BlockNode — content blocks
# ─────────────────────────────────────────────────────────────


@dataclass
class BlockNode(GraphNode):
    """Base for all content blocks."""
    order: int = 0
    region_id: int | None = None
    container_id: int | None = None
    features: BlockFeatures | None = None


# ─────────────────────────────────────────────────────────────
# Inline runs
# ─────────────────────────────────────────────────────────────


@dataclass
class Run:
    """A single run within a paragraph."""
    id: int
    type: str = "text"                # text | bold | italic | citation | hyperlink | footnote_ref | math | field
    text: str = ""
    bold: bool = False
    italic: bool = False
    font_size: float | None = None
    font_name: str | None = None
    is_hidden: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "text": self.text,
            "bold": self.bold,
            "italic": self.italic,
            "font_size": self.font_size,
            "font_name": self.font_name,
            "is_hidden": self.is_hidden,
        }


# ─────────────────────────────────────────────────────────────
# Paragraph block
# ─────────────────────────────────────────────────────────────


@dataclass
class ParagraphBlock(BlockNode):
    """A paragraph with optional inline runs. Role indicates semantic meaning."""
    text: str = ""
    runs: list[Run] = field(default_factory=list)
    role: ParagraphRole = ParagraphRole.BODY
    heading_level: int | None = None

    # Style
    style_name: str = ""
    style_base: str | None = None
    style_hierarchy: list[str] = field(default_factory=list)

    # Visual detection
    is_visual_blank: bool = False
    is_hidden: bool = False

    # Outline + lists
    outline_level: int | None = None
    is_list_item: bool = False
    list_level: int | None = None
    list_id: str | None = None
    numbering_format: str | None = None
    in_table: bool = False

    # Page and section breaks
    page_break_before: bool = False
    page_break_after: bool = False
    section_break_type: str | None = None

    # Spacing
    space_before: float | None = None
    space_after: float | None = None


# ─────────────────────────────────────────────────────────────
# Table
# ─────────────────────────────────────────────────────────────


@dataclass
class TableCell:
    child_ids: list[int] = field(default_factory=list)
    container_id: int = 0


@dataclass
class TableRow:
    cells: list[TableCell] = field(default_factory=list)


@dataclass
class TableBlock(BlockNode):
    rows: list[TableRow] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# List
# ─────────────────────────────────────────────────────────────


@dataclass
class ListItem:
    child_ids: list[int] = field(default_factory=list)
    container_id: int = 0


@dataclass
class ListBlock(BlockNode):
    items: list[ListItem] = field(default_factory=list)
    list_type: str = "bullet"             # ordered | bullet | checklist


# ─────────────────────────────────────────────────────────────
# Figure
# ─────────────────────────────────────────────────────────────


@dataclass
class FigureBlock(BlockNode):
    caption: str | None = None
    image_ref: str | None = None


# ─────────────────────────────────────────────────────────────
# Code block
# ─────────────────────────────────────────────────────────────


@dataclass
class CodeBlock(BlockNode):
    code: str = ""
    language: str | None = None


# ─────────────────────────────────────────────────────────────
# Equation
# ─────────────────────────────────────────────────────────────


@dataclass
class EquationBlock(BlockNode):
    latex: str | None = None
    mathml: str | None = None


# ─────────────────────────────────────────────────────────────
# Structural breaks
# ─────────────────────────────────────────────────────────────


@dataclass
class PageBreak(BlockNode):
    pass


@dataclass
class SectionBreak(BlockNode):
    break_type: str = "next_page"         # next_page | continuous | even_page | odd_page


# ─────────────────────────────────────────────────────────────
# Region node
# ─────────────────────────────────────────────────────────────


@dataclass
class RegionNode(GraphNode):
    """A semantic document region. Blocks reference regions, not the reverse."""
    region_type: RegionType = RegionType.MAIN_CONTENT
    label: str | None = None
    parent_id: int | None = None          # For nesting (e.g., APPENDIX → sub-REFERENCES)
    block_ids: list[int] | None = None    # Child block IDs in this region


# ─────────────────────────────────────────────────────────────
# Edge
# ─────────────────────────────────────────────────────────────


@dataclass
class Edge:
    """A semantic relationship between any two graph nodes."""
    source_id: int
    target_id: int
    type: str
    provenance: Provenance = field(default_factory=Provenance)
    attributes: dict[str, Any] | None = None


# ─────────────────────────────────────────────────────────────
# Block features
# ─────────────────────────────────────────────────────────────


@dataclass
class BlockFeatures:
    word_count: int = 0
    sentence_count: int = 0
    font_size: float | None = None
    font_name: str = ""
    bold: bool = False
    italic: bool = False
    centered: bool = False
    monospace: bool = False
    alignment: str = "left"
    first_line_indent: float = 0.0
    space_before: float | None = None
    space_after: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "font_size": self.font_size,
            "font_name": self.font_name,
            "bold": self.bold,
            "italic": self.italic,
            "centered": self.centered,
            "monospace": self.monospace,
            "alignment": self.alignment,
            "first_line_indent": self.first_line_indent,
            "space_before": self.space_before,
            "space_after": self.space_after,
        }
