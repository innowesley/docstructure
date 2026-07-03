"""Section detector — builds region graph from classified paragraph roles."""

from __future__ import annotations

from typing import Optional, Tuple

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


_SECTION_HEADINGS: list[Tuple[str, RegionType]] = [
    ("abstract", RegionType.ABSTRACT),
    ("introduction", RegionType.INTRODUCTION),
    ("background", RegionType.MAIN_CONTENT),
    ("literature review", RegionType.MAIN_CONTENT),
    ("related work", RegionType.MAIN_CONTENT),
    ("methodology", RegionType.METHODOLOGY),
    ("methods", RegionType.METHODOLOGY),
    ("method", RegionType.METHODOLOGY),
    ("approach", RegionType.METHODOLOGY),
    ("results", RegionType.RESULTS),
    ("findings", RegionType.RESULTS),
    ("analysis", RegionType.DISCUSSION),
    ("discussion", RegionType.DISCUSSION),
    ("conclusion", RegionType.CONCLUSION),
    ("conclusions", RegionType.CONCLUSION),
    ("summary", RegionType.CONCLUSION),
    ("references", RegionType.REFERENCES),
    ("bibliography", RegionType.REFERENCES),
    ("works cited", RegionType.REFERENCES),
    ("acknowledgements", RegionType.REFERENCES),
    ("acknowledgments", RegionType.REFERENCES),
    ("appendix", RegionType.APPENDIX),
    ("appendices", RegionType.APPENDIX),
    ("table of contents", RegionType.TABLE_OF_CONTENTS),
    ("contents", RegionType.TABLE_OF_CONTENTS),
]

_ROLE_REGION_MAP: dict[ParagraphRole, RegionType] = {
    ParagraphRole.ABSTRACT: RegionType.ABSTRACT,
    ParagraphRole.REFERENCE: RegionType.REFERENCES,
    ParagraphRole.APPENDIX: RegionType.APPENDIX,
    ParagraphRole.TOC_ENTRY: RegionType.TABLE_OF_CONTENTS,
}


def _region_for_heading(text: str, lower: str) -> Optional[RegionType]:
    text_lower = lower.strip().rstrip(":")
    for heading_text, rtype in _SECTION_HEADINGS:
        if text_lower == heading_text:
            return rtype
    return None


def _classify_regions(doc: Document) -> list[RegionNode]:
    """Build region tree from classified paragraphs using state machine."""
    paragraphs = doc.paragraphs
    if not paragraphs:
        return []

    state = _RegionState()

    closed_regions: list[Tuple[RegionType, int, list[int]]] = []

    for idx, block in enumerate(paragraphs):
        if state.current is None and idx == 0:
            state.open_region(RegionType.FRONT_MATTER, block.id)
        text = block.text.strip()
        lower = text.lower()
        role = block.role or ParagraphRole.BODY

        new_region_type: Optional[RegionType] = None

        # Heading text match takes priority
        if role == ParagraphRole.HEADING and text:
            new_region_type = _region_for_heading(text, lower)

        # Role-based region transition (for non-heading role signals)
        if new_region_type is None:
            rt = _ROLE_REGION_MAP.get(role)
            if rt is not None and rt != state.current:
                new_region_type = rt

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
