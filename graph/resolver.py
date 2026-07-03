"""Relationship resolver — builds cross-references between nodes."""

import re
from typing import Optional

from docstructure.core.analysis import ReferenceEntry
from docstructure.core.common import ParagraphRole
from docstructure.core.document import Document
from docstructure.core.nodes import Edge, ParagraphBlock, RegionNode


def resolve_relationships(doc: Document) -> None:
    """Resolve cross-references between nodes in the document.

    Builds edges for:
      - heading → section (hierarchical)
      - figure/table → caption
      - citation → reference entry
      - list item → parent list
      - TOC entry → target heading (future: resolved in V2)
    """
    _build_heading_edges(doc)
    _build_citation_edges(doc)
    _build_toc_edges(doc)
    _extract_reference_entries(doc)


def _build_heading_edges(doc: Document) -> None:
    """Build parent→child edges between headings and their sections."""
    paragraphs = doc.paragraphs
    if not paragraphs:
        return

    heading_stack: list[tuple[int, int]] = []

    for block in paragraphs:
        if block.role == ParagraphRole.HEADING and block.heading_level is not None:
            hl = block.heading_level
            while heading_stack and heading_stack[-1][0] >= hl:
                heading_stack.pop()
            if heading_stack:
                parent_id = heading_stack[-1][1]
                doc.edges.append(Edge(
                    source_id=parent_id,
                    target_id=block.id,
                    type="contains",
                    attributes={"hierarchy": "heading"},
                ))
            heading_stack.append((hl, block.id))


def _build_citation_edges(doc: Document) -> None:
    """Build edges from citation text to reference entries."""
    paragraphs = doc.paragraphs
    references = [b for b in paragraphs if b.role == ParagraphRole.REFERENCE]

    for block in paragraphs:
        if block.role == ParagraphRole.REFERENCE:
            continue
        if "(" not in block.text or ")" not in block.text:
            continue
        has_citation = False
        for ref in references:
            first_word = ref.text.split()[0] if ref.text else ""
            if first_word and first_word.strip("().,") in block.text:
                doc.edges.append(Edge(
                    source_id=block.id,
                    target_id=ref.id,
                    type="cites",
                    attributes={},
                ))
                has_citation = True
                break
        if not has_citation and "[" in block.text:
            refs = re.findall(r'\[([^\]]+)\]', block.text)
            if refs:
                for ref_group in refs:
                    parts = ref_group.split(",")
                    for part in parts:
                        part = part.strip()
                        if part.isdigit():
                            idx = int(part) - 1
                            if idx < len(references):
                                doc.edges.append(Edge(
                                    source_id=block.id,
                                    target_id=references[idx].id,
                                    type="cites",
                                    attributes={"citation": f"[{part}]"},
                                ))


def _build_toc_edges(doc: Document) -> None:
    """Build TOC → heading edges from TOC-like paragraphs."""
    paragraphs = doc.paragraphs
    dot_leader = re.compile(r'^([^\.]+)\s*\.{3,}\s*(\d+)$')

    for block in paragraphs:
        if block.role != ParagraphRole.TOC_ENTRY:
            continue
        m = dot_leader.match(block.text.strip())
        if m:
            heading_text = m.group(1).strip()
            page = m.group(2)
            for target in paragraphs:
                if target.role == ParagraphRole.HEADING:
                    if target.text.strip().startswith(heading_text):
                        doc.edges.append(Edge(
                            source_id=block.id,
                            target_id=target.id,
                            type="references",
                            attributes={"page": page},
                        ))
                        break


def _extract_reference_entries(doc: Document) -> None:
    """Extract ReferenceEntry objects from REFERENCE paragraphs."""
    for block in doc.paragraphs:
        if block.role != ParagraphRole.REFERENCE:
            continue
        text = block.text.strip()
        if not text:
            continue

        entry = ReferenceEntry(
            id=doc.next_id(),
            block_id=block.id,
            raw_text=text,
        )

        year_match = re.search(r'\((\d{4})\)', text)
        if year_match:
            entry.year = year_match.group(1)
            after_year = text.split(f"({entry.year})")[-1].strip()
            if after_year:
                title_end = after_year.find(".  ")
                if title_end == -1:
                    title_end = after_year.find(". ")
                if title_end == -1:
                    title_end = after_year.find(".")
                if title_end > 0:
                    entry.title = after_year[:title_end].strip()

        author_match = re.match(r'^([A-Z][^,]+(?:,\s*[A-Z]\.)+)', text)
        if author_match:
            entry.authors = [author_match.group(1)]

        doc.analysis.references.append(entry)
