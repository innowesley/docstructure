"""Pipeline — document analysis pipeline orchestration."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from docstructure.core.document import Document
from docstructure.exceptions import UnsupportedFormatError, ParseError
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

    if not path.exists():
        raise FileNotFoundError(f"File not found: {source}")

    parser_fn = PARSERS.get(ext)
    if parser_fn is None:
        raise UnsupportedFormatError(
            f"Unsupported format: {ext}. Only .docx files are supported in v0.2.0."
        )

    try:
        doc = parser_fn(source)
    except ParseError:
        raise
    except Exception as e:
        raise ParseError(f"Cannot parse '{source}': {e}") from e

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
