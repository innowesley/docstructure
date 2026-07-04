"""APA 7th Edition format detector."""

from __future__ import annotations

import re

from docstructure.core.common import ParagraphRole, RegionType, Signal
from docstructure.core.document import Document
from docstructure.core.nodes import ParagraphBlock, RegionNode
from docstructure.formats.base import FormatDetector, FormatDetection


class APADetector(FormatDetector):
    """Detects APA 7th edition formatting in a document."""

    format_name = "APA"

    def detect(self, doc: Document) -> FormatDetection:
        signals: list[Signal] = []
        evidence: list[str] = []

        s = _score_apa(doc, signals)
        for sig in signals:
            if sig.score > 0:
                evidence.append(f"{sig.name}={sig.score}")

        return FormatDetection(
            format_name="APA",
            confidence=min(1.0, s),
            signals=signals,
            evidence=evidence,
        )


def _score_apa(doc: Document, signals: list[Signal]) -> float:
    """Compute APA confidence score (0.0-1.0)."""
    paragraphs = doc.paragraphs
    regions = doc.regions
    total_weight = 0.0
    score = 0.0

    # Signal 1: Title page (FRONT_MATTER with title paragraph)
    total_weight += 0.15
    has_title_page = _has_title_page(doc)
    signals.append(Signal("title_page", 10 if has_title_page else 0))
    if has_title_page:
        score += 0.15

    # Signal 2: Abstract region
    total_weight += 0.15
    has_abstract = any(r.region_type == RegionType.ABSTRACT for r in regions)
    signals.append(Signal("abstract", 10 if has_abstract else 0))
    if has_abstract:
        score += 0.15

    # Signal 3: References section
    total_weight += 0.15
    has_refs = any(r.region_type == RegionType.REFERENCES for r in regions)
    signals.append(Signal("references_section", 10 if has_refs else 0))
    if has_refs:
        score += 0.15

    # Signal 4: DOI in reference entries
    total_weight += 0.10
    doi_count = _count_doi(doc)
    signals.append(Signal("doi_present", min(10, doi_count * 2)))
    if doi_count > 0:
        score += 0.10

    # Signal 5: Author-date citations
    total_weight += 0.15
    ad_count = _count_author_date_citations(doc)
    signals.append(Signal("author_date_citations", min(10, ad_count)))
    if ad_count >= 2:
        score += 0.15
    elif ad_count == 1:
        score += 0.08

    # Signal 6: Section headings structure
    total_weight += 0.10
    heading_score = _score_heading_structure(doc)
    signals.append(Signal("heading_structure", heading_score))
    score += 0.10 * (heading_score / 10)

    # Signal 7: Serif font (Times New Roman)
    total_weight += 0.10
    font_score = _score_serif_font(doc)
    signals.append(Signal("serif_font", font_score))
    score += 0.10 * (font_score / 10)

    # Signal 8: Running head pattern
    total_weight += 0.10
    has_running_head = _has_running_head(doc)
    signals.append(Signal("running_head", 10 if has_running_head else 0))
    if has_running_head:
        score += 0.10

    if total_weight == 0:
        return 0.0

    return score / total_weight


def _has_title_page(doc: Document) -> bool:
    """Check if document has a title page (FRONT_MATTER with TITLE paragraph)."""
    for region in doc.regions:
        if region.region_type == RegionType.FRONT_MATTER:
            for bid in (region.block_ids or []):
                node = doc.get_node(bid)
                if isinstance(node, ParagraphBlock) and node.role == ParagraphRole.TITLE:
                    return True
    # Fallback: first non-blank paragraph is TITLE
    for p in doc.paragraphs:
        if p.text.strip() and p.role == ParagraphRole.TITLE:
            return True
    return False


def _count_doi(doc: Document) -> int:
    """Count reference entries containing a DOI."""
    count = 0
    for ref in doc.analysis.references:
        text = ref.raw_text
        if "doi.org/10." in text.lower() or "doi:" in text.lower() or re.search(r'10\.\d{4,}/', text):
            count += 1
    return count


def _count_author_date_citations(doc: Document) -> int:
    """Count author-date citation patterns in body paragraphs."""
    pattern = re.compile(r'\([A-Z][a-z]+(?:\s(?:&\s)?[A-Z][a-z]+)?,\s\d{4}[^)]*\)')
    count = 0
    for p in doc.paragraphs:
        if p.role == ParagraphRole.BODY or p.role == ParagraphRole.HEADING:
            count += len(pattern.findall(p.text))
    return count


def _score_heading_structure(doc: Document) -> int:
    """Score heading structure (0-10). APA has specific heading levels."""
    headings = [p for p in doc.paragraphs if p.role == ParagraphRole.HEADING and p.heading_level is not None]
    if not headings:
        return 0
    levels = [h.heading_level for h in headings if h.heading_level is not None]
    if not levels:
        return 0
    max_level = max(levels)
    min_level = min(levels)
    if max_level >= 2 and min_level == 1:
        return 10
    if max_level >= 1:
        return 5
    return 2


def _score_serif_font(doc: Document) -> int:
    """Check if body text uses serif font (Times New Roman 12pt). 0-10."""
    serif_fonts = {"times new roman", "times", "georgia", "palatino", "garamond", "bookman"}
    body_paras = [p for p in doc.paragraphs if p.role == ParagraphRole.BODY and p.features]
    if not body_paras:
        return 0
    match_count = 0
    for p in body_paras:
        fn = (p.features.font_name or "").lower()
        fs = p.features.font_size
        if any(s in fn for s in serif_fonts):
            match_count += 1
    ratio = match_count / len(body_paras)
    if ratio >= 0.8:
        return 10
    if ratio >= 0.5:
        return 6
    if ratio >= 0.2:
        return 3
    return 0


def _has_running_head(doc: Document) -> bool:
    """Check for running head pattern (short title in header area)."""
    running_head_pattern = re.compile(r'Running\s+head', re.IGNORECASE)
    for p in doc.paragraphs:
        if running_head_pattern.search(p.text):
            return True
    return False
