"""MLA 9th edition validation rules."""

from __future__ import annotations

import re

from docstructure.core.common import ParagraphRole, RegionType, Severity
from docstructure.core.document import Document
from docstructure.validate.base import Rule, RuleResult


class MlaNoTitlePageRule(Rule):
    """MLA 9.01 — No separate title page."""

    def __init__(self):
        super().__init__("mla-9.01", Severity.INFO)

    def check(self, doc: Document) -> list[RuleResult]:
        for region in doc.regions:
            if region.region_type == RegionType.FRONT_MATTER:
                block_count = len(region.block_ids or [])
                if block_count > 4:
                    return [RuleResult(
                        rule_name=self.name,
                        passed=False,
                        severity=self.severity,
                        message=f"FRONT_MATTER has {block_count} blocks — likely a title page (MLA typically has no separate title page)",
                    )]
                if block_count <= 4:
                    return [RuleResult(
                        rule_name=self.name,
                        passed=True,
                        severity=self.severity,
                        message=f"FRONT_MATTER has {block_count} blocks — consistent with MLA header format",
                    )]
        return [RuleResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="No FRONT_MATTER region — consistent with MLA (no title page)",
        )]


class MlaHeaderRule(Rule):
    """MLA 9.02 — Header with name/instructor/course/date."""

    def __init__(self):
        super().__init__("mla-9.02", Severity.WARNING)

    def check(self, doc: Document) -> list[RuleResult]:
        paras = doc.paragraphs[:6]
        date_pattern = re.compile(
            r'\b\d{1,2}\s+(January|February|March|April|May|June|'
            r'July|August|September|October|November|December)\s+\d{4}\b',
            re.IGNORECASE,
        )
        header_candidates = 0
        has_date = False
        first_left = False

        for i, p in enumerate(paras):
            text = p.text.strip()
            if not text:
                continue
            is_left = not p.features.centered if p.features else True
            is_short = len(text) < 80
            if i == 0 and is_left and is_short:
                first_left = True
            if is_left and is_short:
                header_candidates += 1
            if date_pattern.search(text):
                has_date = True

        if header_candidates >= 4 and has_date:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"MLA-style header detected: {header_candidates} left-aligned lines including a date",
            )]
        if header_candidates >= 3:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Partial MLA-style header: {header_candidates} left-aligned lines (expected 4: name, instructor, course, date)",
            )]
        if first_left:
            return [RuleResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"Only {header_candidates} left-aligned header line(s) found (MLA expects 4: name, instructor, course, date)",
            )]
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message="No MLA-style header detected (expected: name, instructor, course, date left-aligned)",
        )]


class MlaWorksCitedRule(Rule):
    """MLA 9.03 — Works Cited section present."""

    def __init__(self):
        super().__init__("mla-9.03", Severity.ERROR)

    def check(self, doc: Document) -> list[RuleResult]:
        for region in doc.regions:
            if region.region_type == RegionType.REFERENCES:
                label = (region.label or "").lower()
                if "works cited" in label:
                    ref_count = len(region.block_ids or [])
                    return [RuleResult(
                        rule_name=self.name,
                        passed=True,
                        severity=self.severity,
                        message=f"Works Cited section found with {ref_count} entries",
                    )]
        for p in doc.paragraphs:
            if p.role == ParagraphRole.HEADING and p.text.strip().lower().rstrip(":") == "works cited":
                return [RuleResult(
                    rule_name=self.name,
                    passed=True,
                    severity=self.severity,
                    message="Works Cited heading found",
                )]
        ref_count = sum(1 for p in doc.paragraphs if p.role == ParagraphRole.REFERENCE)
        if ref_count > 0:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Found {ref_count} reference entries (section heading not detected as 'Works Cited')",
            )]
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message="No Works Cited section found (required for MLA)",
        )]


class MlaAuthorPageCitationsRule(Rule):
    """MLA 9.04 — In-text citations use author-page format."""

    def __init__(self):
        super().__init__("mla-9.04", Severity.ERROR)

    def check(self, doc: Document) -> list[RuleResult]:
        patterns = [
            re.compile(r'\([A-Z][a-z]+(?:\s(?:et\s+al\.?))?\s+\d+(?:-\d+)?\)'),
            re.compile(r'\([A-Z][a-z]+\s\d+(?:-\d+)?\)'),
        ]
        count = 0
        for p in doc.paragraphs:
            if p.role == ParagraphRole.BODY or p.role == ParagraphRole.HEADING:
                for pat in patterns:
                    count += len(pat.findall(p.text))

        if count >= 2:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Found {count} author-page citations",
                diagnostics={"citation_count": count},
            )]
        if count >= 1:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Found {count} author-page citation(s)",
                diagnostics={"citation_count": count},
            )]
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message="No author-page citations found (MLA uses author-page format: (Smith 23))",
        )]


class MlaHangingIndentRule(Rule):
    """MLA 9.05 — Hanging indent on Works Cited entries."""

    def __init__(self):
        super().__init__("mla-9.05", Severity.WARNING)

    def check(self, doc: Document) -> list[RuleResult]:
        ref_paras = [p for p in doc.paragraphs if p.role == ParagraphRole.REFERENCE and p.features]
        if not ref_paras:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="No reference entries to check for hanging indent",
            )]
        hanging_count = 0
        for p in ref_paras:
            if p.features.first_line_indent is not None and p.features.first_line_indent < 0:
                hanging_count += 1
            elif p.style_name and "hanging" in p.style_name.lower():
                hanging_count += 1
        total = len(ref_paras)
        ratio = hanging_count / total
        if ratio >= 0.8:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"{hanging_count}/{total} reference entries have hanging indent",
                diagnostics={"hanging_count": hanging_count, "total": total},
            )]
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message=f"Only {hanging_count}/{total} reference entries have hanging indent (MLA requires hanging indent)",
            diagnostics={"hanging_count": hanging_count, "total": total},
        )]
