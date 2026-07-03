"""DocStructure configuration — default pipeline wiring and registrations."""

from docstructure.classifier.paragraph import classify_paragraphs
from docstructure.classifier.sections import build_regions
from docstructure.features import extract_features
from docstructure.graph.resolver import resolve_relationships
from docstructure.normalizer.normalize import normalize
from docstructure.validate.base import Rule, validate


class Pipeline:
    """Default analysis pipeline stages."""
    stages = [
        ("normalize", normalize),
        ("extract_features", extract_features),
        ("classify_paragraphs", classify_paragraphs),
        ("build_regions", build_regions),
        ("resolve_relationships", resolve_relationships),
    ]

    @classmethod
    def run(cls, doc, start: str | None = None, end: str | None = None):
        started = start is None
        for name, stage in cls.stages:
            if name == start:
                started = True
            if name == end:
                stage(doc)
                break
            if started:
                stage(doc)


# Built-in rules
DEFAULT_RULES: list[Rule] = [
    # Imported in validate.base
]

# Parser registry
PARSERS: dict[str, str] = {
    ".docx": "docstructure.parser.docx.DOCXParser",
    # Future: ".pdf": "docstructure.parser.pdf.PDFParser",
}
