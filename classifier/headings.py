"""Heading normalization and section transition confidence scoring."""

from __future__ import annotations

import re
from typing import Optional


_NUMBER_RE = re.compile(r'^(?:\d+(?:\.\d+)*|[IVXLCDM]+)[\.\)\s]+')
_CHAPTER_RE = re.compile(r'^(?:chapter|section|part)\s+\d+[\s:\-–—]+\s*', re.I)


def normalize_heading(text: str) -> str:
    """Normalize heading text for vocabulary lookup.

    Strips numbering, Roman numerals, chapter/section prefixes,
    trailing punctuation, collapses whitespace, lowercases.
    """
    t = text.strip()
    t = _NUMBER_RE.sub('', t)
    t = _CHAPTER_RE.sub('', t)
    t = t.lower().strip().rstrip(".:;")
    return re.sub(r'\s+', ' ', t)


# ── Reference heading vocabulary ──────────────────────────────

# Canonical reference section names with semantic weight (0.0–0.5).
# Normalization handles numbering, punctuation, and casing variations
# (e.g. "5. References" → "references").
REFERENCE_VOCABULARY: dict[str, float] = {
    "references": 0.5,
    "reference list": 0.5,
    "bibliography": 0.5,
    "works cited": 0.5,
    "works consulted": 0.5,
    "literature cited": 0.5,
    "cited references": 0.4,
    "selected bibliography": 0.4,
    "selected references": 0.4,
    "references and notes": 0.5,
}

# Partial-match keywords — used when the heading is not an exact vocabulary match
# but contains reference-related terms.
REFERENCE_KEYWORDS: set[str] = {"reference", "bibliograph", "citation", "cited"}

# Default confidence threshold for opening a REFERENCES region.
TRANSITION_THRESHOLD: float = 0.8


# ── Confidence scoring ────────────────────────────────────────


def compute_reference_confidence(
    normalized: str,
    heading_score: int,
    look_ahead_ref_scores: list[float],
    in_main_body: bool = True,
) -> float:
    """Compute confidence (0.0–1.0) that a heading starts a REFERENCES region.

    Combines four signals:
      1. Heading semantics   (0.0–0.5) — vocabulary exact/partial match
      2. Heading formatting  (0.0–0.3) — heading_score from classifier
      3. Look-ahead evidence (0.0–0.5) — reference-like paragraphs following
      4. Context bonus       (0.0–0.1) — already past front matter

    Returns 0.0–1.0.
    """
    c = 0.0

    # 1. Heading semantics
    if normalized in REFERENCE_VOCABULARY:
        c += REFERENCE_VOCABULARY[normalized]
    else:
        for kw in REFERENCE_KEYWORDS:
            if kw in normalized:
                c += 0.3
                break

    # 2. Heading formatting
    if heading_score >= 5:
        c += 0.3
    elif heading_score >= 2:
        c += 0.2
    elif heading_score >= 1:
        c += 0.1

    # 3. Look-ahead evidence
    if look_ahead_ref_scores:
        strong = sum(1 for s in look_ahead_ref_scores if s >= 5)
        ratio = strong / len(look_ahead_ref_scores)
        c += min(0.5, ratio * 0.5)

    # 4. Context bonus — references belong after main body
    if in_main_body:
        c += 0.1

    return min(c, 1.0)


def should_open_references(
    normalized: str,
    heading_score: int,
    look_ahead_ref_scores: list[float],
    in_main_body: bool = True,
    threshold: float = TRANSITION_THRESHOLD,
) -> bool:
    """Decide whether to open a REFERENCES region based on confidence threshold."""
    return (
        compute_reference_confidence(
            normalized, heading_score, look_ahead_ref_scores, in_main_body,
        ) >= threshold
    )
