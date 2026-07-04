"""DocStructure — document structure analysis engine.

Public API (stable until v1.0):
    analyze()       — full analysis pipeline
    parse()         — parse only (no analysis)
    detect_format() — detect academic format (APA/MLA/IEEE)
    validate()      — validate against format rules
    serialize()     — Document → dict
    to_json()       — Document → JSON string
    to_file()       — Document → JSON file
"""

from docstructure.pipeline import run_pipeline as analyze
from docstructure.output.json import to_json, to_file, serialize
from docstructure.formats import detect_best as detect_format
from docstructure.validate.base import validate
from docstructure.core.document import Document
from docstructure.core.nodes import ClassificationResult, ClassifierInfo

from docstructure._version import __version__
__all__ = [
    "analyze",
    "parse",
    "detect_format",
    "validate",
    "serialize",
    "to_json",
    "to_file",
    "ClassificationResult",
    "ClassifierInfo",
    "__version__",
]


def parse(source: str) -> Document:
    """Parse a document file into a Document object (no analysis pipeline)."""
    from docstructure.parser.docx import DOCXParser
    from pathlib import Path

    path = Path(source)
    ext = path.suffix.lower()
    if ext != ".docx":
        from docstructure.exceptions import UnsupportedFormatError
        raise UnsupportedFormatError(
            f"Unsupported format: {ext}. Only .docx files are supported in v0.2.0."
        )
    if not path.exists():
        raise FileNotFoundError(f"File not found: {source}")

    parser = DOCXParser()
    return parser.parse(str(path))
