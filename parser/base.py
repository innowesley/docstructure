"""Parser registry and abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from docstructure.core.document import Document


# ─────────────────────────────────────────────────────────────
# Parser capabilities
# ─────────────────────────────────────────────────────────────


@dataclass
class ParserCapabilities:
    """What a parser can produce. Validators check this to avoid false negatives."""
    supports_layout: bool = False
    supports_fonts: bool = True
    supports_tables: bool = True
    supports_images: bool = True
    supports_fields: bool = True
    supports_comments: bool = False
    supports_track_changes: bool = True


# ─────────────────────────────────────────────────────────────
# Parser ABC
# ─────────────────────────────────────────────────────────────


class Parser(ABC):
    """Base class for all format-specific parsers.

    A parser produces physical blocks only — it never assigns semantic roles.
    Classification happens in a later pipeline stage.
    """

    @abstractmethod
    def parse(self, source: str | bytes, **kwargs: Any) -> Document:
        """Parse a document into a Document graph.

        Args:
            source: File path (str) or raw bytes.
            **kwargs: Parser-specific options.

        Returns:
            Document with nodes populated from physical structure.
        """

    @property
    @abstractmethod
    def capabilities(self) -> ParserCapabilities: ...

    @classmethod
    @abstractmethod
    def supported_mime_types(cls) -> list[str]: ...


# ─────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────


class ParserRegistry:
    """MIME-type-based parser registry."""

    def __init__(self) -> None:
        self._parsers: dict[str, type[Parser]] = {}

    def register(self, mime_type: str, parser_cls: type[Parser]) -> None:
        self._parsers[mime_type] = parser_cls

    def get(self, mime_type: str) -> type[Parser] | None:
        return self._parsers.get(mime_type)

    def detect(self, path: str) -> type[Parser] | None:
        """Detect parser by file extension."""
        import mimetypes
        mime, _ = mimetypes.guess_type(path)
        if mime and mime in self._parsers:
            return self._parsers[mime]
        return self._parsers.get("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
