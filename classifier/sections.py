"""Section detector — builds region graph from classified paragraph roles."""

from __future__ import annotations

from typing import List, Optional, Tuple

from docstructure.core.common import ParagraphRole, Provenance, RegionType
from docstructure.core.document import Document
from docstructure.core.nodes import Edge, RegionNode


# ─────────────────────────────────────────────────────────────
# Region type ↔ role mapping
# ─────────────────────────────────────────────────────────────

_region_map: dict[RegionType, set[ParagraphRole]] = {
    RegionType.TITLE_PAGE: {ParagraphRole.TITLE, ParagraphRole.AUTHOR, ParagraphRole.METADATA},
    RegionType.ABSTRACT: {ParagraphRole.ABSTRACT},
    RegionType.INTRODUCTION: {ParagraphRole.HEADING, ParagraphRole.BODY},
    RegionType.MAIN_CONTENT: {ParagraphRole.HEADING, ParagraphRole.BODY},
    RegionType.REFERENCES: {ParagraphRole.REFERENCE, ParagraphRole.HEADING},
    RegionType.APPENDIX: {ParagraphRole.APPENDIX, ParagraphRole.BODY, ParagraphRole.HEADING},
    RegionType.TABLE_OF_CONTENTS: {ParagraphRole.TOC_ENTRY, ParagraphRole.HEADING},
    RegionType.FRONT_MATTER: {ParagraphRole.TITLE, ParagraphRole.METADATA, ParagraphRole.AUTHOR},
    RegionType.BACK_MATTER: {ParagraphRole.REFERENCE},
}

# Region types that can contain headings
_heading_signaled: set[RegionType] = {
    RegionType.ABSTRACT,
    RegionType.INTRODUCTION,
    RegionType.MAIN_CONTENT,
    RegionType.METHODOLOGY,
    RegionType.RESULTS,
    RegionType.DISCUSSION,
    RegionType.CONCLUSION,
    RegionType.APPENDIX,
    RegionType.BACK_MATTER,
}


# ─────────────────────────────────────────────────────────────
# State machine (adapted from acewriter V4)
# ─────────────────────────────────────────────────────────────


class _RegionState:
    """Tracks current region during state machine traversal."""
    def __init__(self):
        self.current: Optional[RegionType] = RegionType.FRONT_MATTER
        self.start_block_id: int = -1
        self.start_block_index: int = -1
        self.blocks_in_region: list[int] = []
        self.diagnostics: list[str] = []
        self.region_stack: list[RegionType] = []  # for nesting

    def open_region(self, region_type: RegionType, block_index: int, block_id: int) -> None:
        self.close_region(block_index, block_id)
        self.current = region_type
        self.start_block_id = block_id
        self.start_block_index = block_index
        self.blocks_in_region = [block_id]
        self.region_stack.append(region_type)

    def extend_region(self, block_id: int) -> None:
        self.blocks_in_region.append(block_id)

    def close_region(self, block_index: int, block_id: int) -> Optional[Tuple[RegionType, int, int, list[int]]]:
        if self.current is None or not self.blocks_in_region:
            return None
        result = (self.current, self.start_block_id, block_id, self.blocks_in_region)
        self.current = None
        self.start_block_id = -1
        self.blocks_in_region = []
        return result

    def finalize(self) -> Optional[Tuple[RegionType, int, int, list[int]]]:
        return self.close_region(-1, -1)


def _region_for_heading(text: str, lower: str) -> Optional[RegionType]:
    # Check section names
    text_lower = lower.strip().rstrip(":")
    for heading_text, rtype in _SECTION_HEADINGS:
        if text_lower == heading_text:
            return rtype
    return None


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


def _classify_regions(doc: Document) -> list[RegionNode]:
    """Build region tree from classified paragraphs."""
    paragraphs = doc.paragraphs
    if not paragraphs:
        return []

    state = _RegionState()
    first = paragraphs[0]
    state.open_region(RegionType.FRONT_MATTER, 0, first.id)

    for idx, block in enumerate(paragraphs):
        text = block.text.strip()
        lower = text.lower()
        role = block.role or ParagraphRole.BODY

        # Detect region change from heading
        if role == ParagraphRole.HEADING and text:
            new_region = _region_for_heading(text, lower)
            if new_region is not None:
                # Close current region, open new one
                state.close_region(idx, block.id)
                state.open_region(new_region, idx, block.id)
                continue

        # Default: extend current region
        if state.current is not None:
            state.extend_region(block.id)
        else:
            # No open region (shouldn't happen)
            state.open_region(RegionType.MAIN_CONTENT, idx, block.id)
            state.extend_region(block.id)

    # Close final region
    state.finalize()

    # Build RegionNode objects
    regions: list[RegionNode] = []
    for idx, block in enumerate(paragraphs):
        # For now, each block becomes a single-block region
        # Full state machine will merge in V2
        region_type = RegionType.MAIN_CONTENT
        text = block.text.strip().lower()
        role = block.role or ParagraphRole.BODY

        if role == ParagraphRole.TITLE:
            region_type = RegionType.TITLE_PAGE
        elif role == ParagraphRole.ABSTRACT:
            region_type = RegionType.ABSTRACT
        elif role == ParagraphRole.TOC_ENTRY:
            region_type = RegionType.TABLE_OF_CONTENTS
        elif role == ParagraphRole.REFERENCE:
            region_type = RegionType.REFERENCES
        elif role == ParagraphRole.APPENDIX:
            region_type = RegionType.APPENDIX
        elif role == ParagraphRole.HEADING:
            for heading_text, rtype in _SECTION_HEADINGS:
                if text.rstrip(":") == heading_text:
                    region_type = rtype
                    break
            else:
                if region_type == RegionType.MAIN_CONTENT:
                    region_type = RegionType.MAIN_CONTENT  # keep default

        region = RegionNode(
            id=doc.next_id(),
            region_type=region_type,
            label=block.text[:80] if block.text else "",
            block_ids=[block.id],
        )
        region.provenance = Provenance(
            confidence=0.7,
            produced_by="section_classifier/v1",
            version="1.0",
            evidence=[f"role={role.value}"],
        )
        regions.append(region)

    return regions


def build_regions(doc: Document) -> None:
    """Build region tree and attach to document."""
    regions = _classify_regions(doc)
    for region in regions:
        doc.add_node(region)
        doc.edges.append(Edge(
            source_id=region.id,
            target_id=region.block_ids[0],
            type="contains",
            attributes={},
        ))
