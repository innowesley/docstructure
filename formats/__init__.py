"""Format registry — auto-discovers and runs format detectors.

Detectors auto-register via ``FormatDetector.__init_subclass__``.
Importing detector modules triggers registration.
"""

from __future__ import annotations

from typing import Type

from docstructure.core.document import Document
from docstructure.formats.base import FormatDetector, FormatDetection, _detectors_registry

# Import all detector modules to trigger __init_subclass__ registration
from docstructure.formats import apa  # noqa: F401
from docstructure.formats import mla  # noqa: F401
from docstructure.formats import ieee  # noqa: F401


def detect_all(doc: Document) -> list[FormatDetection]:
    """Run ALL registered detectors, return sorted by confidence descending."""
    results: list[FormatDetection] = []
    for cls in _detectors_registry.values():
        try:
            detector = cls()
            result = detector.detect(doc)
            results.append(result)
        except Exception:
            results.append(FormatDetection(
                format_name=cls.format_name,
                confidence=0.0,
                evidence=["detector_error"],
            ))
    results.sort(key=lambda r: r.confidence, reverse=True)
    return results


def detect_best(doc: Document, threshold: float = 0.3) -> FormatDetection | None:
    """Return the highest-confidence detection (or None if all below threshold)."""
    results = detect_all(doc)
    if results and results[0].confidence >= threshold:
        return results[0]
    return None
