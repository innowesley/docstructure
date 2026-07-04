"""Analysis results — diagnostics, reference entries, format detection, validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from docstructure.core.common import Provenance, Severity


# ─────────────────────────────────────────────────────────────
# Diagnostic
# ─────────────────────────────────────────────────────────────


@dataclass
class Location:
    """A specific location in the document graph."""
    node_id: int
    run_id: int | None = None
    offset: int | None = None          # Unicode codepoint offset
    length: int | None = None          # Length in codepoints

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"node_id": self.node_id}
        if self.run_id is not None:
            d["run_id"] = self.run_id
        if self.offset is not None:
            d["offset"] = self.offset
        if self.length is not None:
            d["length"] = self.length
        return d


@dataclass
class Diagnostic:
    """A single validation finding — modeled after compiler diagnostics."""
    severity: Severity
    rule_id: str
    message: str
    location: Location | None = None
    fix: str | None = None
    provenance: Provenance = field(default_factory=Provenance)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "severity": self.severity.value,
            "rule_id": self.rule_id,
            "message": self.message,
        }
        if self.location is not None:
            d["location"] = self.location.to_dict()
        if self.fix is not None:
            d["fix"] = self.fix
        d["provenance"] = self.provenance.to_dict()
        return d


# ─────────────────────────────────────────────────────────────
# Reference entry
# ─────────────────────────────────────────────────────────────


@dataclass
class ReferenceEntry:
    """A reference extracted from a reference paragraph."""
    id: int
    block_id: int
    raw_text: str
    authors: list[str] | None = None
    year: str | None = None
    title: str | None = None
    journal: str | None = None
    doi: str | None = None
    url: str | None = None
    pages: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "block_id": self.block_id,
            "raw_text": self.raw_text,
        }
        for k in ("authors", "year", "title", "journal", "doi", "url", "pages"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        return d


# ─────────────────────────────────────────────────────────────
# Format detection
# ─────────────────────────────────────────────────────────────


@dataclass
class FormatDetectionResult:
    """Combined format detection output."""
    detections: list[dict[str, Any]] = field(default_factory=list)
    winner: str | None = None
    winner_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "detections": self.detections,
            "winner": self.winner,
            "winner_confidence": self.winner_confidence,
        }


# ─────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────


@dataclass
class ValidationRuleResult:
    """Outcome of a single validation rule within a format check."""
    rule_id: str
    passed: bool
    severity: str = "warning"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    """Complete validation output for a document."""
    format: str = ""
    compliance_score: float = 0.0
    rule_results: list[ValidationRuleResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "compliance_score": self.compliance_score,
            "rule_results": [r.to_dict() for r in self.rule_results],
        }


# ─────────────────────────────────────────────────────────────
# DocumentAnalysis
# ─────────────────────────────────────────────────────────────


@dataclass
class DocumentAnalysis:
    """Computed results — diagnostics, extracted knowledge, format detection, validation."""
    diagnostics: list[Diagnostic] = field(default_factory=list)
    references: list[ReferenceEntry] = field(default_factory=list)
    format_detection: FormatDetectionResult | None = None
    validation: ValidationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "diagnostics": [diag.to_dict() for diag in self.diagnostics],
            "references": [r.to_dict() for r in self.references],
        }
        if self.format_detection is not None:
            d["format_detection"] = self.format_detection.to_dict()
        if self.validation is not None:
            d["validation"] = self.validation.to_dict()
        return d
