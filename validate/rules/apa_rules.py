"""APA 7th edition validation rules."""

from __future__ import annotations

import re

from docstructure.core.common import ParagraphRole, RegionType, Severity
from docstructure.core.document import Document
from docstructure.core.nodes import ParagraphBlock
from docstructure.validate.base import Rule, RuleResult


class ApaRunningHeadRule(Rule):
    """APA 7.01 — Running head present on title page."""

    def __init__(self):
        super().__init__("apa-7.01", Severity.WARNING)

    def check(self, doc: Document) -> list[RuleResult]:
        pattern = re.compile(r'Running\s+head', re.IGNORECASE)
        for p in doc.paragraphs:
            if pattern.search(p.text):
                return [RuleResult(
                    rule_name=self.name,
                    passed=True,
                    severity=self.severity,
                    message="Running head found in document",
                )]
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message="No running head detected (expected on title page for APA)",
        )]


class ApaAbstractRule(Rule):
    """APA 7.02 — Abstract present in research papers."""

    def __init__(self):
        super().__init__("apa-7.02", Severity.INFO)

    def check(self, doc: Document) -> list[RuleResult]:
        has_abstract = any(r.region_type == RegionType.ABSTRACT for r in doc.regions)
        if has_abstract:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="Abstract section found",
            )]
        # Check for "Abstract" heading text
        for p in doc.paragraphs:
            if p.role == ParagraphRole.HEADING and p.text.strip().lower().rstrip(":") == "abstract":
                return [RuleResult(
                    rule_name=self.name,
                    passed=True,
                    severity=self.severity,
                    message="Abstract heading found (paragraph-level)",
                )]
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message="No abstract section found (recommended for APA research papers)",
        )]


class ApaReferencesRule(Rule):
    """APA 7.03 — References section present."""

    def __init__(self):
        super().__init__("apa-7.03", Severity.ERROR)

    def check(self, doc: Document) -> list[RuleResult]:
        has_refs = any(r.region_type == RegionType.REFERENCES for r in doc.regions)
        ref_count = sum(1 for p in doc.paragraphs if p.role == ParagraphRole.REFERENCE)
        if has_refs and ref_count > 0:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"References section with {ref_count} entries found",
                diagnostics={"reference_count": ref_count},
            )]
        if has_refs:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="References section found (no classified references)",
            )]
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message="No references section found (required for APA)",
        )]


class ApaDoiRule(Rule):
    """APA 7.04 — DOI/URL present in reference entries."""

    def __init__(self):
        super().__init__("apa-7.04", Severity.WARNING)

    def check(self, doc: Document) -> list[RuleResult]:
        ref_paras = [p for p in doc.paragraphs if p.role == ParagraphRole.REFERENCE]
        if not ref_paras:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="No references to check for DOI",
            )]

        doi_pattern = re.compile(r'10\.\d{4,}/[^\s]+|doi\.org|doi:', re.IGNORECASE)
        with_doi = sum(1 for p in ref_paras if doi_pattern.search(p.text))
        total = len(ref_paras)
        ratio = with_doi / total if total > 0 else 0

        if ratio >= 0.8:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"{with_doi}/{total} references have DOI/URL",
                diagnostics={"with_doi": with_doi, "total": total},
            )]
        return [RuleResult(
            rule_name=self.name,
            passed=ratio >= 0.5,
            severity=self.severity,
            message=f"Only {with_doi}/{total} references have DOI/URL (APA recommends DOI for all references)",
            diagnostics={"with_doi": with_doi, "total": total},
        )]


class ApaHeadingOrderRule(Rule):
    """APA 7.05 — Heading levels do not skip (e.g., H1 → H3 without H2)."""

    def __init__(self):
        super().__init__("apa-7.05", Severity.WARNING)

    def check(self, doc: Document) -> list[RuleResult]:
        skipped: list[int] = []
        prev_level = 0
        for block in doc.paragraphs:
            if block.role == ParagraphRole.HEADING and block.heading_level is not None:
                hl = block.heading_level
                if hl > prev_level + 1 and prev_level > 0:
                    skipped.append(block.id)
                if hl > 0:
                    prev_level = hl

        if skipped:
            return [RuleResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"Found {len(skipped)} heading level skip(s) (e.g., H1→H3)",
                locations=[{"block_id": bid} for bid in skipped],
                diagnostics={"skipped_blocks": skipped},
            )]
        return [RuleResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="Heading levels are sequential",
        )]


class ApaFontRule(Rule):
    """APA 7.06 — Font is Times New Roman 12pt or equivalent serif."""

    def __init__(self):
        super().__init__("apa-7.06", Severity.INFO)

    def check(self, doc: Document) -> list[RuleResult]:
        serif_fonts = {"times new roman", "times", "georgia", "palatino", "garamond", "bookman"}
        body_paras = [p for p in doc.paragraphs if p.role == ParagraphRole.BODY and p.features]
        if not body_paras:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="No body text to check font",
            )]
        match_count = 0
        size_ok = 0
        for p in body_paras:
            fn = (p.features.font_name or "").lower()
            fs = p.features.font_size
            if any(s in fn for s in serif_fonts):
                match_count += 1
                if fs is not None and 11 <= fs <= 13:
                    size_ok += 1
        total = len(body_paras)
        font_ratio = match_count / total
        size_ratio = size_ok / total if match_count > 0 else 0

        if font_ratio >= 0.8 and size_ratio >= 0.8:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Font is serif ~12pt in {int(font_ratio*100)}% of body",
                diagnostics={"serif_ratio": font_ratio, "size_ok_ratio": size_ratio},
            )]
        msg_parts = []
        if font_ratio < 0.8:
            msg_parts.append(f"only {int(font_ratio*100)}% use serif font")
        elif size_ratio < 0.8:
            msg_parts.append("font size not ~12pt")
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message=f"APA recommends Times New Roman 12pt; {', '.join(msg_parts)}",
            diagnostics={"serif_ratio": font_ratio, "size_ok_ratio": size_ratio},
        )]


class ApaAuthorDateRule(Rule):
    """APA 7.08 — Citations use author-date format."""

    def __init__(self):
        super().__init__("apa-7.08", Severity.ERROR)

    def check(self, doc: Document) -> list[RuleResult]:
        pattern = re.compile(r'\([A-Z][a-z]+(?:\s(?:&\s)?[A-Z][a-z]+)?,\s*\d{4}[^)]*\)')
        count = 0
        for p in doc.paragraphs:
            if p.role == ParagraphRole.BODY or p.role == ParagraphRole.HEADING:
                count += len(pattern.findall(p.text))

        if count >= 2:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Found {count} author-date citations",
                diagnostics={"citation_count": count},
            )]
        if count >= 1:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Found {count} author-date citation(s)",
                diagnostics={"citation_count": count},
            )]
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message="No author-date citations (Author, Year) found (required for APA)",
        )]
