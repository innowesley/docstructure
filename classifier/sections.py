"""Section detector — builds region graph from classified paragraph roles."""

from __future__ import annotations

from typing import Optional, Tuple

from docstructure.classifier.headings import (
    normalize_heading,
    should_open_references,
    REFERENCE_VOCABULARY,
)
from docstructure.core.common import ParagraphRole, Provenance, RegionType
from docstructure.core.document import Document
from docstructure.core.nodes import Edge, RegionNode


# ── State machine ──


class _RegionState:
    def __init__(self):
        self.current: Optional[RegionType] = None
        self.start_block_id: int = -1
        self.blocks_in_region: list[int] = []
        self.region_stack: list[RegionType] = []

    def open_region(self, region_type: RegionType, block_id: int) -> None:
        self.current = region_type
        self.start_block_id = block_id
        self.blocks_in_region = []
        self.region_stack.append(region_type)

    def extend_region(self, block_id: int) -> None:
        self.blocks_in_region.append(block_id)

    def close_region(self) -> Optional[Tuple[RegionType, int, list[int]]]:
        if self.current is None or not self.blocks_in_region:
            return None
        result = (self.current, self.start_block_id, self.blocks_in_region)
        self.current = None
        self.start_block_id = -1
        self.blocks_in_region = []
        return result

    def finalize(self) -> Optional[Tuple[RegionType, int, list[int]]]:
        return self.close_region()


_ROLE_REGION_MAP: dict[ParagraphRole, RegionType] = {
    ParagraphRole.ABSTRACT: RegionType.ABSTRACT,
    ParagraphRole.REFERENCE: RegionType.REFERENCES,
    ParagraphRole.APPENDIX: RegionType.APPENDIX,
    ParagraphRole.TOC_ENTRY: RegionType.TABLE_OF_CONTENTS,
}

_PRE_BODY_REGIONS: set[RegionType] = {
    RegionType.FRONT_MATTER, RegionType.ABSTRACT, RegionType.TABLE_OF_CONTENTS,
}


def _in_main_body(state: _RegionState) -> bool:
    """Check if the document has progressed past front matter."""
    return state.current not in _PRE_BODY_REGIONS


def _gather_ref_scores(paragraphs: list, idx: int, lookahead: int = 3) -> list[float]:
    """Collect reference scores for paragraphs following *idx*."""
    scores: list[float] = []
    end = min(len(paragraphs), idx + 1 + lookahead)
    for i in range(idx + 1, end):
        c = paragraphs[i].classification
        ref = c.scores.get("reference", 0) if c and c.scores else 0
        scores.append(ref)
    return scores


def _heading_score(paragraph) -> int:
    c = paragraph.classification
    return int(c.scores.get("heading", 0)) if c and c.scores else 0


def _classify_regions(doc: Document) -> list[RegionNode]:
    """Build region tree from classified paragraphs using state machine.

    Uses section-transition confidence scoring for REFERENCES region
    detection (see classifier/headings.py). Non-REFERENCES headings
    default to MAIN_CONTENT (generic document analysis approach).
    """
    paragraphs = doc.paragraphs
    if not paragraphs:
        return []

    state = _RegionState()

    closed_regions: list[Tuple[RegionType, int, list[int]]] = []

    for idx, block in enumerate(paragraphs):
        if state.current is None and idx == 0:
            state.open_region(RegionType.FRONT_MATTER, block.id)
        text = block.text.strip()
        role = block.role or ParagraphRole.BODY

        new_region_type: Optional[RegionType] = None

        # Signal A: Heading-driven transition
        #   - REFERENCES region uses confidence scoring (semantics + formatting + evidence)
        #   - All other headings default to MAIN_CONTENT (generic document analysis engine)
        if role == ParagraphRole.HEADING and text:
            normalized = normalize_heading(text)
            new_region_type = RegionType.MAIN_CONTENT

            if state.current != RegionType.REFERENCES:
                look_ahead = _gather_ref_scores(paragraphs, idx)
                if should_open_references(
                    normalized,
                    _heading_score(block),
                    look_ahead,
                    in_main_body=_in_main_body(state),
                ):
                    new_region_type = RegionType.REFERENCES
            else:
                # Already in REFERENCES — only leave if heading has strong formatting
                # evidence (score >= 3) indicating a real new section.
                if _heading_score(block) < 3:
                    new_region_type = None

        # Signal B: Role-based region transition
        #   (catches un-headed sections via paragraph-level classification)
        if new_region_type is None:
            rt = _ROLE_REGION_MAP.get(role)
            if rt is not None and rt != state.current:
                if rt == RegionType.REFERENCES:
                    look_ahead = _gather_ref_scores(paragraphs, idx)
                    strong = sum(1 for s in look_ahead if s >= 5)
                    if strong >= 2:
                        new_region_type = rt
                else:
                    new_region_type = rt

        # Persistence: once in REFERENCES, don't leave without good reason
        if new_region_type is not None:
            if state.current == RegionType.REFERENCES and new_region_type != RegionType.REFERENCES:
                if role != ParagraphRole.HEADING:
                    new_region_type = None

        if new_region_type is not None:
            result = state.close_region()
            if result is not None:
                closed_regions.append(result)
            state.open_region(new_region_type, block.id)
            state.extend_region(block.id)
            continue

        if state.current is not None:
            state.extend_region(block.id)
        else:
            state.open_region(RegionType.MAIN_CONTENT, block.id)
            state.extend_region(block.id)

    result = state.finalize()
    if result is not None:
        closed_regions.append(result)

    regions: list[RegionNode] = []
    for rtype, start_id, block_ids in closed_regions:
        first_block = doc.get_node(start_id)
        label = first_block.text[:80] if first_block and hasattr(first_block, 'text') else ""
        region = RegionNode(
            id=doc.next_id(),
            region_type=rtype,
            label=label,
            block_ids=block_ids,
        )
        region.provenance = Provenance(
            confidence=0.7,
            produced_by="section_classifier/v1",
            version="1.0",
            evidence=[f"region_type={rtype.value}"],
        )
        regions.append(region)

    return regions


def build_regions(doc: Document) -> None:
    regions = _classify_regions(doc)
    for region in regions:
        doc.add_node(region)
        for bid in (region.block_ids or []):
            doc.edges.append(Edge(
                source_id=region.id,
                target_id=bid,
                type="contains",
                attributes={},
            ))
