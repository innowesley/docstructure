"""IEEE format detector."""

from __future__ import annotations

import re

from docstructure.core.common import ParagraphRole, RegionType, Signal
from docstructure.core.document import Document
from docstructure.core.nodes import ParagraphBlock
from docstructure.formats.base import FormatDetector, FormatDetection


class IEEEDetector(FormatDetector):
    """Detects IEEE formatting in a document."""

    format_name = "IEEE"

    def detect(self, doc: Document) -> FormatDetection:
        signals: list[Signal] = []
        evidence: list[str] = []

        s = _score_ieee(doc, signals)
        for sig in signals:
            if sig.score > 0:
                evidence.append(f"{sig.name}={sig.score}")

        return FormatDetection(
            format_name="IEEE",
            confidence=min(1.0, s),
            signals=signals,
            evidence=evidence,
        )


def _score_ieee(doc: Document, signals: list[Signal]) -> float:
    paragraphs = doc.paragraphs
    regions = doc.regions
    total_weight = 0.0
    score = 0.0

    # Signal 1: Numbered references [1], [2], etc.
    total_weight += 0.25
    ref_score = _score_numbered_references(doc)
    signals.append(Signal("numbered_references", ref_score))
    score += 0.25 * (ref_score / 10)

    # Signal 2: Roman numeral section headings (I, II, III)
    total_weight += 0.20
    roman_score = _score_roman_headings(doc)
    signals.append(Signal("roman_headings", roman_score))
    score += 0.20 * (roman_score / 10)

    # Signal 3: Absence of author-date + presence of [n] in body
    total_weight += 0.15
    bracket_citations = _count_bracket_citations(doc)
    author_date = _count_author_date_citations(doc)
    if bracket_citations >= 2 and author_date == 0:
        signals.append(Signal("bracket_citations", min(10, bracket_citations)))
        score += 0.15
    elif bracket_citations >= 2:
        signals.append(Signal("bracket_citations", min(10, bracket_citations)))
        score += 0.08
    else:
        signals.append(Signal("bracket_citations", 0))

    # Signal 4: Section sequence (Abstract → Introduction → ... → References)
    total_weight += 0.20
    seq_score = _score_section_sequence(doc)
    signals.append(Signal("section_sequence", seq_score))
    score += 0.20 * (seq_score / 10)

    # Signal 5: Figure captions "Fig. n."
    total_weight += 0.10
    fig_score = _score_figure_captions(doc)
    signals.append(Signal("figure_captions", fig_score))
    score += 0.10 * (fig_score / 10)

    # Signal 6: Serif font (Times New Roman 10pt)
    total_weight += 0.10
    font_score = _score_ieee_font(doc)
    signals.append(Signal("ieee_font", font_score))
    score += 0.10 * (font_score / 10)

    if total_weight == 0:
        return 0.0

    return score / total_weight


def _score_numbered_references(doc: Document) -> int:
    """Check if reference paragraphs start with [n] pattern. 0-10."""
    ref_paras = [p for p in doc.paragraphs if p.role == ParagraphRole.REFERENCE]
    if not ref_paras:
        ref_paras = [p for p in doc.paragraphs if p.role == ParagraphRole.BODY and p.text.strip().startswith("[")]
    if not ref_paras:
        return 0
    bracket_count = sum(1 for p in ref_paras if re.match(r'^\[\d+\]', p.text.strip()))
    if not ref_paras:
        return 0
    ratio = bracket_count / len(ref_paras)
    if ratio >= 0.8:
        return 10
    if ratio >= 0.5:
        return 6
    if ratio >= 0.2:
        return 3
    return 0


def _score_roman_headings(doc: Document) -> int:
    """Check for Roman numeral headings like I., II., III. 0-10."""
    roman_pattern = re.compile(r'^(X{0,3}(?:IX|IV|V?I{0,3}))[\.\)]\s', re.IGNORECASE)
    headings = [p for p in doc.paragraphs if p.role == ParagraphRole.HEADING]
    if not headings:
        return 0
    roman_count = sum(1 for h in headings if roman_pattern.match(h.text.strip()))
    if len(headings) == 0:
        return 0
    ratio = roman_count / len(headings)
    if ratio >= 0.5:
        return 10
    if ratio >= 0.3:
        return 6
    if ratio >= 0.1:
        return 3
    return 0


def _count_bracket_citations(doc: Document) -> int:
    """Count [n] citation patterns in body text."""
    pattern = re.compile(r'\[(\d+)(?:,\s*\d+)*\]')
    count = 0
    for p in doc.paragraphs:
        if p.role == ParagraphRole.BODY or p.role == ParagraphRole.HEADING:
            count += len(pattern.findall(p.text))
    return count


def _count_author_date_citations(doc: Document) -> int:
    """Count author-date citation patterns in body text."""
    pattern = re.compile(r'\([A-Z][a-z]+(?:\s(?:&\s)?[A-Z][a-z]+)?,\s\d{4}[^)]*\)')
    count = 0
    for p in doc.paragraphs:
        if p.role == ParagraphRole.BODY or p.role == ParagraphRole.HEADING:
            count += len(pattern.findall(p.text))
    return count


def _score_section_sequence(doc: Document) -> int:
    """Check for IEEE-like section sequence. 0-10."""
    heading_texts = []
    for p in doc.paragraphs:
        if p.role == ParagraphRole.HEADING:
            heading_texts.append(p.text.strip().lower().rstrip(":"))

    if not heading_texts:
        return 0

    score = 0
    # IEEE typically has: Abstract, Introduction, ... , Conclusion, References
    expected = ["abstract", "introduction", "conclusion", "references"]
    total_found = 0
    for exp in expected:
        for ht in heading_texts:
            if exp in ht:
                total_found += 1
                break

    if total_found >= 3:
        score = 10
    elif total_found == 2:
        score = 7
    elif total_found == 1:
        score = 3
    return score


def _score_figure_captions(doc: Document) -> int:
    """Check for 'Fig. n' pattern in captions. 0-10."""
    fig_pattern = re.compile(r'Fig\.?\s*\d+', re.IGNORECASE)
    count = 0
    for p in doc.paragraphs:
        if p.role == ParagraphRole.CAPTION:
            count += 1
            if fig_pattern.search(p.text):
                return 10
    return min(count * 2, 6) if count > 0 else 0


def _score_ieee_font(doc: Document) -> int:
    """Check if body uses serif font ~10pt (IEEE default is TNR 10pt). 0-10."""
    serif_fonts = {"times new roman", "times", "georgia", "palatino"}
    body_paras = [p for p in doc.paragraphs if p.role == ParagraphRole.BODY and p.features]
    if not body_paras:
        return 0
    match_count = 0
    for p in body_paras:
        fn = (p.features.font_name or "").lower()
        fs = p.features.font_size
        if any(s in fn for s in serif_fonts):
            if fs is None or (9 <= fs <= 11):
                match_count += 1
    ratio = match_count / len(body_paras)
    if ratio >= 0.8:
        return 10
    if ratio >= 0.5:
        return 6
    if ratio >= 0.2:
        return 3
    return 0
