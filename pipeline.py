"""Pipeline — document analysis pipeline orchestration."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from docstructure.core.document import Document
from docstructure.normalizer.normalize import normalize
from docstructure.features import extract_features
from docstructure.classifier.paragraph import classify_paragraphs
from docstructure.classifier.sections import build_regions
from docstructure.graph.resolver import resolve_relationships


def _resolve_docx(source: str | Path) -> Document:
    from docstructure.parser.docx import DOCXParser
    parser = DOCXParser()
    return parser.parse(str(source))


PARSERS: dict[str, Callable[[str | Path], Document]] = {
    ".docx": _resolve_docx,
}


def run_pipeline(source: str, verbose: bool = False) -> Document:
    """Full analysis pipeline."""
    path = Path(source)
    ext = path.suffix.lower()

    parser_fn = PARSERS.get(ext)
    if parser_fn is None:
        print(f"Unsupported file type: {ext}", file=sys.stderr)
        sys.exit(1)

    if not path.exists():
        print(f"File not found: {source}", file=sys.stderr)
        sys.exit(1)

    try:
        doc = parser_fn(source)
    except Exception as e:
        print(f"Error: Cannot parse '{source}': {e}", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"  Parsed: {len(doc.paragraphs)} paragraphs, {len(doc.nodes)} total nodes")

    normalize(doc)
    if verbose:
        print(f"  Normalized")

    extract_features(doc)
    if verbose:
        print(f"  Features extracted")

    classify_paragraphs(doc)
    if verbose:
        print(f"  Paragraphs classified")

    build_regions(doc)
    if verbose:
        print(f"  Regions built")

    resolve_relationships(doc)
    if verbose:
        print(f"  Relationships resolved")

    return doc
