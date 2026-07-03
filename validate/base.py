"""Validation — rule-based document structure validation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from docstructure.core.common import Severity
from docstructure.core.document import Document


@dataclass
class RuleResult:
    """Outcome of a single validation rule."""
    rule_name: str
    passed: bool
    severity: Severity = Severity.WARNING
    message: str = ""
    locations: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


class Rule(ABC):
    """Base class for validation rules. Extend to implement custom checks."""

    def __init__(self, name: str, severity: Severity = Severity.WARNING):
        self.name = name
        self.severity = severity

    @abstractmethod
    def check(self, doc: Document) -> list[RuleResult]:
        ...


class NoBodyTextRule(Rule):
    """Warn if document has no BODY paragraphs."""
    def __init__(self):
        super().__init__("no_body_text", Severity.WARNING)

    def check(self, doc: Document) -> list[RuleResult]:
        from docstructure.core.common import ParagraphRole
        body_count = sum(1 for b in doc.paragraphs if b.role == ParagraphRole.BODY and not b.is_visual_blank and b.text.strip())
        return [RuleResult(
            rule_name=self.name,
            passed=body_count > 0,
            severity=self.severity,
            message=f"Document has {body_count} body paragraphs" if body_count > 0 else "Document has no body paragraphs",
            diagnostics={"body_count": body_count},
        )]


class MissingSectionsRule(Rule):
    """Warn if document has no main sections."""
    def __init__(self):
        super().__init__("missing_sections", Severity.WARNING)

    def check(self, doc: Document) -> list[RuleResult]:
        from docstructure.core.common import RegionType
        from docstructure.core.nodes import RegionNode
        skip_types = {RegionType.FRONT_MATTER, RegionType.BACK_MATTER}
        section_count = sum(1 for n in doc.nodes if isinstance(n, RegionNode) and n.region_type not in skip_types)
        return [RuleResult(
            rule_name=self.name,
            passed=section_count > 1,
            severity=self.severity,
            message=f"Document has {section_count} sections" if section_count > 1 else "Document has insufficient sections",
            diagnostics={"section_count": section_count},
        )]


class HeadingOrderRule(Rule):
    """Warn if heading levels skip (e.g., H1 → H3 without H2)."""
    def __init__(self):
        super().__init__("heading_order", Severity.WARNING)

    def check(self, doc: Document) -> list[RuleResult]:
        from docstructure.core.common import ParagraphRole
        skipped: list[int] = []
        prev_level = 0
        for block in doc.paragraphs:
            if block.role == ParagraphRole.HEADING and block.heading_level is not None:
                hl = block.heading_level
                if hl > prev_level + 1 and prev_level > 0:
                    skipped.append(block.id)
                if hl > 0:
                    prev_level = hl

        return [RuleResult(
            rule_name=self.name,
            passed=len(skipped) == 0,
            severity=self.severity,
            message=f"Found {len(skipped)} skipped heading levels" if skipped else "Heading levels are sequential",
            locations=[{"block_id": bid} for bid in skipped],
            diagnostics={"skipped_blocks": skipped},
        )]


_DEFAULT_RULES: list[Rule] = [
    NoBodyTextRule(),
    MissingSectionsRule(),
    HeadingOrderRule(),
]


def validate(doc: Document, rules: list[Rule] | None = None) -> list[RuleResult]:
    """Run all rules against the document."""
    if rules is None:
        rules = _DEFAULT_RULES
    results: list[RuleResult] = []
    for rule in rules:
        results.extend(rule.check(doc))
    return results
