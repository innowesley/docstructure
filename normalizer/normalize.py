"""Normalization stage — clean up raw parser output before feature extraction."""

import unicodedata
import re

from docstructure.core.document import Document
from docstructure.core.nodes import ParagraphBlock, Run


def normalize(doc: Document) -> None:
    """Normalize a parsed document in place.

    Applies to all ParagraphBlocks:
      - Unicode normalization (NFC)
      - Smart quotes → straight quotes
      - NBSP → regular spaces
      - Control characters stripped
      - Hidden runs removed
      - Adjacent identical runs merged
      - is_visual_blank recomputed
    """
    for block in doc.paragraphs:
        _normalize_text(block)
        _normalize_runs(block)
        _merge_identical_runs(block)
        _recompute_visual_blank(block)


def _normalize_text(block: ParagraphBlock) -> None:
    text = block.text
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u00a0", " ")
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', "", text)
    block.text = text


def _normalize_runs(block: ParagraphBlock) -> None:
    filtered: list[Run] = []
    for run in block.runs:
        if run.is_hidden:
            continue
        text = run.text
        text = unicodedata.normalize("NFC", text)
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        text = text.replace("\u00a0", " ")
        run.text = text
        filtered.append(run)
    block.runs = filtered


def _merge_identical_runs(block: ParagraphBlock) -> None:
    if not block.runs:
        return
    merged: list[Run] = [block.runs[0]]
    for run in block.runs[1:]:
        prev = merged[-1]
        if (_runs_identical(prev, run)):
            prev.text += run.text
        else:
            merged.append(run)
    block.runs = merged


def _runs_identical(a: Run, b: Run) -> bool:
    return (
        a.type == b.type
        and a.bold == b.bold
        and a.italic == b.italic
        and a.font_size == b.font_size
        and a.font_name == b.font_name
        and a.is_hidden == b.is_hidden
    )


def _recompute_visual_blank(block: ParagraphBlock) -> None:
    if block.text.strip():
        block.is_visual_blank = False
        return
    for run in block.runs:
        t = run.text or ""
        if t.strip() and not t.strip("\u00a0"):
            block.is_visual_blank = False
            return
    block.is_visual_blank = True
