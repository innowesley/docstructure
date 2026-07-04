"""Format detection base — FormatDetector ABC and data types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from docstructure.core.common import Signal
from docstructure.core.document import Document


@dataclass
class FormatDetection:
    """Result from a single format detector."""
    format_name: str
    confidence: float
    signals: list[Signal] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


# Import the registry late to avoid circular imports
_detectors_registry: dict[str, type] = {}


class FormatDetector(ABC):
    """Base class for format detectors.

    Each detector scores a document for how well it matches a specific
    academic/citation format (APA, MLA, IEEE, etc.).

    All detectors run independently and results are sorted by confidence.

    Subclasses auto-register via ``__init_subclass__``. Set ``format_name``
    as a class attribute.
    """

    format_name: str = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.format_name:
            _detectors_registry[cls.format_name] = cls

    @property
    def name(self) -> str:
        return self.format_name

    @abstractmethod
    def detect(self, doc: Document) -> FormatDetection:
        """Score 0.0–1.0 how well this document matches the format.

        Returns:
            FormatDetection with confidence, signals, and evidence.
            confidence=0.0 means 'not this format'.
        """
