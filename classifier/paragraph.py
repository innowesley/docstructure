"""Paragraph classifier — assigns semantic roles to paragraph blocks."""

from __future__ import annotations

import re

from docstructure.core.common import ParagraphRole, Provenance, Signal
from docstructure.core.document import Document
from docstructure.core.nodes import (
    BlockFeatures,
    ClassificationResult,
    ClassifierInfo,
    ParagraphBlock,
)


# ─────────────────────────────────────────────────────────────
# Constants (from acewriter analyzer.py)
# ─────────────────────────────────────────────────────────────

SECTION_NAMES: set[str] = {
    "introduction", "background", "literature review", "related work",
    "methodology", "methods", "method", "approach",
    "results", "findings", "analysis",
    "discussion",
    "conclusion", "conclusions", "summary",
    "abstract", "executive summary",
    "references", "bibliography", "works cited",
    "acknowledgements", "acknowledgments",
    "appendix", "appendices",
    "index", "glossary",
    "list of figures", "list of tables", "list of algorithms",
    "list of listings", "table of contents", "contents",
    "outlook", "overview", "purpose", "scope", "objectives",
    "design", "procedure", "materials", "participants",
    "limitations", "future work", "recommendations",
    "cost analysis", "revenue analysis", "swot analysis",
    "executive summary", "company overview", "market analysis",
    "financial performance", "metrics", "key findings",
}

SECTION_WORDS: set[str] = {
    "introduction", "background", "literature", "review",
    "methodology", "method", "methods", "approach",
    "results", "findings", "analysis", "analyses",
    "discussion",
    "conclusion", "conclusions", "summary",
    "abstract",
    "references", "bibliography",
    "acknowledgements", "acknowledgments",
    "appendix", "appendices",
    "index", "glossary",
    "outlook", "overview", "purpose", "scope", "objectives",
    "design", "procedure", "materials", "participants",
    "limitations", "recommendations",
}

METADATA_PLACEHOLDERS: set[str] = {
    "student name", "student", "name", "author", "written by", "prepared by",
    "course", "course name", "class", "section",
    "instructor", "professor", "lecturer", "teacher",
    "date", "submitted", "submission date", "due date",
    "assignment", "paper", "essay", "student id", "id",
    "university", "college", "department", "school",
    "semester", "term", "year",
    "institution", "faculty", "supervisor", "adviser", "advisor",
}

NUMBERED_HEADING = re.compile(r'^(\d+(?:\.\d+)*)[\.\)]\s')
CHAPTER_HEADING = re.compile(r'^chapter\s+\d+', re.IGNORECASE)
ROMAN_HEADING = re.compile(r'^(X{0,3}(?:IX|IV|V?I{0,3}))[\.\)]\s', re.IGNORECASE)

# Reference features (citations, author names, years) overlap naturally
# with academic body text. To prevent body paragraphs with incidental
# citations from being classified as REFERENCE (which triggers early
# back-matter in the region state machine), the classifier requires:
#   1. reference_score >= REFERENCE_MIN_SCORE (strength check)
#   2. reference_score >= body_score + REFERENCE_MARGIN (dominance check)
#      — reference evidence must clearly dominate body evidence.
REFERENCE_MIN_SCORE = 5
REFERENCE_MARGIN = 2


# ─────────────────────────────────────────────────────────────
# Score functions (adapted from acewriter V4)
# ─────────────────────────────────────────────────────────────


class ParagraphScores:
    """Score vector for classification. No winner selected — consumers decide."""
    def __init__(self):
        self.body = 0
        self.title = 0
        self.heading = 0
        self.metadata = 0
        self.reference = 0
        self.caption = 0
        self.toc = 0
        self.abstract = 0
        self.appendix = 0
        self.list_score = 0

    def confidence(self) -> float:
        vals = [self.body, self.title, self.heading, self.metadata,
                self.reference, self.caption, self.toc, self.abstract,
                self.appendix, self.list_score]
        total = sum(vals)
        if total == 0:
            return 0.0
        return max(vals) / total

    def winner(self) -> ParagraphRole:
        candidates: list[tuple[int | float, int, ParagraphRole]] = [
            (self.body, 0, ParagraphRole.BODY),
            (self.title, 1, ParagraphRole.TITLE),
            (self.heading, 2, ParagraphRole.HEADING),
            (self.metadata, 3, ParagraphRole.METADATA),
            (self.reference, 4, ParagraphRole.REFERENCE),
            (self.caption, 5, ParagraphRole.CAPTION),
            (self.toc, 6, ParagraphRole.TOC_ENTRY),
            (self.abstract, 7, ParagraphRole.ABSTRACT),
            (self.appendix, 8, ParagraphRole.APPENDIX),
        ]
        best = max(candidates, key=lambda x: (x[0], -x[1]))
        if best[0] == 0:
            return ParagraphRole.BODY
        return best[2]


def _is_title_case(text: str) -> bool:
    return text.istitle() if text else False


def _ends_with_period(text: str) -> bool:
    return text.endswith(".")


def _lowercase_ratio(text: str) -> float:
    if not text:
        return 0.0
    lower = sum(1 for c in text if c.islower())
    return lower / len(text)


def _score_body(features: BlockFeatures, text: str) -> int:
    score = 0
    if features.sentence_count > 1:
        score += 3
    if features.word_count > 15:
        score += 2
    if not features.centered:
        score += 1
    if _ends_with_period(text):
        score += 1
    if not _is_title_case(text) or features.sentence_count > 1:
        score += 1
    return score


def _score_title(features: BlockFeatures, text: str) -> int:
    score = 0
    if features.centered:
        score += 3
    if features.word_count < 12:
        score += 1
    if _is_title_case(text):
        score += 1
    if not _ends_with_period(text):
        score += 1
    if features.bold and features.centered:
        score += 2
    return score


def _score_heading(features: BlockFeatures, style_name: str, text: str) -> int:
    score = 0
    if style_name.lower().startswith("heading"):
        score += 5
    if features.bold and features.word_count < 20:
        score += 3
    if features.centered and features.word_count < 15:
        score += 2
    if features.font_size is not None and features.font_size >= 14 and features.word_count < 15:
        score += 3
    text_lower = text.strip().lower().rstrip(":")
    if text_lower in SECTION_NAMES:
        score += 3
    elif any(w in SECTION_WORDS for w in text_lower.split()):
        score += 2
    if NUMBERED_HEADING.match(text.strip()):
        score += 2
    if CHAPTER_HEADING.match(text.strip()):
        score += 3
    return score


def _score_metadata(features: BlockFeatures, text: str) -> int:
    score = 0
    text_lower = text.strip().lower().rstrip(".")
    if text_lower in METADATA_PLACEHOLDERS:
        score += 5
    elif any(text.lower().startswith(kw) for kw in METADATA_PLACEHOLDERS):
        score += 4
    elif any(kw in text_lower for kw in METADATA_PLACEHOLDERS):
        score += 2
    if features.word_count < 8:
        score += 2
    return score


def _score_reference(features: BlockFeatures, text: str) -> int:
    score = 0
    if features.word_count > 5:
        score += 1
    if text and text[0].isdigit() and "." in text[:4]:
        score += 3
    if text.startswith("["):
        score += 2

    # APA-style: Author (Year) pattern
    has_year = bool(re.search(r'\(\d{4}\)', text))
    if has_year:
        score += 3

    # APA-style: Author, A. / Author, A. A. pattern
    if has_year and "," in text:
        score += 2

    # Multiple commas suggest full citation
    if text.count(",") >= 3:
        score += 1

    # Starts with author name (capitalized word, not a heading word)
    if has_year and text[0].isupper():
        score += 1

    # Contains journal-like pattern (Volume, pages)
    if re.search(r'\d+\(\d+\)', text):
        score += 2

    # Contains DOI or URL
    if "doi" in text.lower() or "http" in text.lower():
        score += 2

    return score


def _score_caption(features: BlockFeatures, text: str) -> int:
    score = 0
    if text.startswith(("Figure", "Table", "Fig.")):
        score += 4
    if ":" in text[:20]:
        score += 2
    if features.word_count < 15:
        score += 2
    return score


def _score_toc(features: BlockFeatures, style_name: str, text: str) -> int:
    score = 0
    if "toc" in style_name.lower():
        score += 4
    if ".." in text:
        score += 3
    if text.lower().startswith(("table of contents", "contents")):
        score += 3
    return score


def _score_abstract(features: BlockFeatures, style_name: str, text: str) -> int:
    score = 0
    text_lower = text.strip().lower().rstrip(":")
    if text_lower in ("abstract", "executive summary"):
        return 5
    return 0


def _score_appendix(features: BlockFeatures, text: str) -> int:
    score = 0
    text_lower = text.strip().lower().rstrip(":")
    if text_lower.startswith("appendix"):
        score += 5
    return score


def _compute_scores(block: ParagraphBlock) -> ParagraphScores:
    f = block.features or BlockFeatures()
    text = block.text
    s = ParagraphScores()
    s.body = _score_body(f, text)
    s.title = _score_title(f, text)
    s.heading = _score_heading(f, block.style_name, text)
    s.metadata = _score_metadata(f, text)
    s.reference = _score_reference(f, text)
    s.caption = _score_caption(f, text)
    s.toc = _score_toc(f, block.style_name, text)
    s.abstract = _score_abstract(f, block.style_name, text)
    s.appendix = _score_appendix(f, text)
    return s


def _determine_role(scores: ParagraphScores, text: str) -> ParagraphRole:
    if text.strip() and scores.winner() == ParagraphRole.HEADING and scores.heading >= 2:
        return ParagraphRole.HEADING
    if scores.reference >= REFERENCE_MIN_SCORE and scores.reference >= scores.body + REFERENCE_MARGIN:
        return ParagraphRole.REFERENCE
    if scores.caption >= 3:
        return ParagraphRole.CAPTION
    if scores.toc >= 3:
        return ParagraphRole.TOC_ENTRY
    if scores.abstract >= 3:
        return ParagraphRole.ABSTRACT
    if scores.appendix >= 3:
        return ParagraphRole.APPENDIX
    if scores.metadata >= 4:
        return ParagraphRole.METADATA
    if scores.body >= 2:
        return ParagraphRole.BODY
    if scores.title >= 3 and scores.body < 3:
        return ParagraphRole.TITLE
    return ParagraphRole.BODY


# ─────────────────────────────────────────────────────────────
# Main entry
# ─────────────────────────────────────────────────────────────


def classify_paragraphs(doc: Document) -> None:
    """Classify every ParagraphBlock in the document.

    Assigns role, heading_level, and provenance to each block.
    """
    for block in doc.paragraphs:
        # Skip table cell paragraphs — they are children of TableCell, not standalone
        if block.in_table:
            block.role = ParagraphRole.BODY
            block.classification = ClassificationResult(
                label=ParagraphRole.BODY,
                confidence=0.0,
                classifier=ClassifierInfo(name="paragraph_classifier", version="1.0"),
            )
            block.provenance = Provenance(
                confidence=0.0,
                produced_by="paragraph_classifier/v1",
                evidence=["in_table"],
            )
            continue

        if block.is_visual_blank or not block.text.strip():
            block.role = ParagraphRole.BODY
            block.classification = ClassificationResult(
                label=ParagraphRole.BODY,
                confidence=0.0,
                classifier=ClassifierInfo(name="paragraph_classifier", version="1.0"),
            )
            block.provenance = Provenance(
                confidence=0.0,
                produced_by="paragraph_classifier/v1",
                evidence=["blank_paragraph"],
            )
            continue

        scores = _compute_scores(block)
        role = _determine_role(scores, block.text)
        confidence = scores.confidence()

        score_dict: dict[str, float] = {
            k: float(v) for k, v in vars(scores).items()
            if isinstance(v, (int, float))
        }

        block.classification = ClassificationResult(
            label=role,
            confidence=confidence,
            scores=score_dict if score_dict else None,
            classifier=ClassifierInfo(name="paragraph_classifier", version="1.0"),
        )
        block.role = role
        block.provenance = Provenance(
            confidence=confidence,
            produced_by="paragraph_classifier/v1",
            version="1.0",
            evidence=[f"score_{role.value}={getattr(scores, role.value, 0)}"],
        )

        # Heading level
        if role == ParagraphRole.HEADING:
            hl = None
            if block.style_name.lower().startswith("heading"):
                m = re.search(r'heading\s+(\d+)', block.style_name, re.IGNORECASE)
                if m:
                    hl = int(m.group(1))
            if hl is None:
                m = NUMBERED_HEADING.match(block.text.strip())
                if m:
                    hl = m.group(1).count(".") + 1
            if hl is None and CHAPTER_HEADING.match(block.text.strip()):
                hl = 1
            block.heading_level = hl or 1

        # Heading level from outline
        if block.outline_level is not None and block.outline_level > 0:
            if block.heading_level is None or block.outline_level < block.heading_level:
                block.heading_level = block.outline_level
