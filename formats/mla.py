"""MLA 9th Edition format detector."""

from __future__ import annotations

import re

from docstructure.core.common import ParagraphRole, RegionType, Signal
from docstructure.core.document import Document
from docstructure.core.nodes import ParagraphBlock, RegionNode
from docstructure.formats.base import FormatDetector, FormatDetection


class MLADetector(FormatDetector):
    """Detects MLA 9th edition formatting in a document."""

    format_name = "MLA"

    def detect(self, doc: Document) -> FormatDetection:
        signals: list[Signal] = []
        evidence: list[str] = []

        s = _score_mla(doc, signals)
        for sig in signals:
            if sig.score > 0:
                evidence.append(f"{sig.name}={sig.score}")

        return FormatDetection(
            format_name="MLA",
            confidence=min(1.0, s),
            signals=signals,
            evidence=evidence,
        )


def _score_mla(doc: Document, signals: list[Signal]) -> float:
    paragraphs = doc.paragraphs
    regions = doc.regions
    total_weight = 0.0
    score = 0.0

    # Signal 1: No separate title page
    total_weight += 0.15
    no_title_page = _has_no_title_page(doc)
    signals.append(Signal("no_title_page", 10 if no_title_page else 0))
    if no_title_page:
        score += 0.15

    # Signal 2: MLA header (name, instructor, course, date)
    total_weight += 0.20
    header_score = _score_mla_header(doc)
    signals.append(Signal("mla_header", header_score))
    score += 0.20 * (header_score / 10)

    # Signal 3: Works Cited section (not "References")
    total_weight += 0.20
    works_cited = _has_works_cited(doc)
    signals.append(Signal("works_cited", 10 if works_cited else 0))
    if works_cited:
        score += 0.20

    # Signal 4: Author-page citations
    total_weight += 0.20
    ap_count = _count_author_page_citations(doc)
    signals.append(Signal("author_page_citations", min(10, ap_count)))
    if ap_count >= 2:
        score += 0.20
    elif ap_count == 1:
        score += 0.10

    # Signal 5: Hanging indent on citations
    total_weight += 0.15
    hanging_score = _score_hanging_indent(doc)
    signals.append(Signal("hanging_indent", hanging_score))
    score += 0.15 * (hanging_score / 10)

    # Signal 6: First-line header pattern (name left-aligned)
    total_weight += 0.10
    first_line_para = paragraphs[0] if paragraphs else None
    if first_line_para and first_line_para.text.strip() and not first_line_para.features.centered:
        signals.append(Signal("first_line_left", 8))
        score += 0.10 * 0.8
    else:
        signals.append(Signal("first_line_left", 0))

    if total_weight == 0:
        return 0.0

    return score / total_weight


def _has_no_title_page(doc: Document) -> bool:
    """MLA rarely has a separate title page. FRONT_MATTER should be minimal or absent."""
    for region in doc.regions:
        if region.region_type == RegionType.FRONT_MATTER:
            block_count = len(region.block_ids or [])
            if block_count <= 4:
                return True
            return False
    # No FRONT_MATTER region at all — even stronger signal for no title page
    return True


def _score_mla_header(doc: Document) -> int:
    """Score MLA header pattern: name → instructor → course → date (0-10)."""
    # Look for 4 short left-aligned paragraphs at the beginning
    paras = doc.paragraphs[:6]
    header_candidates = 0
    date_pattern = re.compile(r'\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b', re.IGNORECASE)
    has_date = False

    for p in paras:
        text = p.text.strip()
        if not text:
            continue
        is_left = not p.features.centered if p.features else True
        is_short = len(text) < 80
        is_single_line = p.features.word_count < 15 if p.features else True
        if is_left and is_short and is_single_line:
            header_candidates += 1
        if date_pattern.search(text):
            has_date = True

    if header_candidates >= 3 and has_date:
        return 10
    if header_candidates >= 4:
        return 8
    if header_candidates >= 2:
        return 5
    if header_candidates >= 1:
        return 2
    return 0


def _has_works_cited(doc: Document) -> bool:
    """Check if the references section is titled 'Works Cited'."""
    for region in doc.regions:
        if region.region_type == RegionType.REFERENCES:
            label = (region.label or "").lower()
            if "works cited" in label:
                return True
    # Also check paragraph text for references heading
    for p in doc.paragraphs:
        if p.role == ParagraphRole.REFERENCE:
            continue
        text = p.text.strip().lower()
        if text == "works cited":
            return True
    return False


def _count_author_page_citations(doc: Document) -> int:
    """Count author-page citation patterns in body text."""
    # Patterns: (Author #), (Author #-#), (Author et al. #)
    patterns = [
        re.compile(r'\([A-Z][a-z]+(?:\s(?:et\s+al\.?))?\s+\d+(?:-\d+)?\)'),
        re.compile(r'\([A-Z][a-z]+\s\d+(?:-\d+)?\)'),
    ]
    count = 0
    for p in doc.paragraphs:
        if p.role == ParagraphRole.BODY or p.role == ParagraphRole.HEADING:
            for pat in patterns:
                count += len(pat.findall(p.text))
    return count


def _score_hanging_indent(doc: Document) -> int:
    """Check if reference paragraphs have hanging indent (first_line_indent < 0). 0-10."""
    ref_paras = [p for p in doc.paragraphs if p.role == ParagraphRole.REFERENCE and p.features]
    if not ref_paras:
        return 0
    hanging_count = 0
    for p in ref_paras:
        if p.features.first_line_indent is not None and p.features.first_line_indent < 0:
            hanging_count += 1
        elif p.style_name and "hanging" in p.style_name.lower():
            hanging_count += 1
    ratio = hanging_count / len(ref_paras)
    if ratio >= 0.8:
        return 10
    if ratio >= 0.5:
        return 6
    if ratio >= 0.2:
        return 3
    return 0
