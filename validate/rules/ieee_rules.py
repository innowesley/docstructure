"""IEEE validation rules."""

from __future__ import annotations

import re

from docstructure.core.common import ParagraphRole, Severity
from docstructure.core.document import Document
from docstructure.validate.base import Rule, RuleResult


class IeeeNumberedReferencesRule(Rule):
    """IEEE-R01 — References are numbered [1], [2], etc."""

    def __init__(self):
        super().__init__("ieee-r01", Severity.ERROR)

    def check(self, doc: Document) -> list[RuleResult]:
        ref_paras = [p for p in doc.paragraphs if p.role == ParagraphRole.REFERENCE]
        if not ref_paras:
            return [RuleResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message="No references section found (required for IEEE)",
            )]
        bracket_count = sum(1 for p in ref_paras if re.match(r'^\[\d+\]', p.text.strip()))
        total = len(ref_paras)
        if bracket_count == total and total > 0:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"All {total} references use IEEE bracket format [1], [2], etc.",
                diagnostics={"bracket_count": bracket_count, "total": total},
            )]
        if bracket_count > 0:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"{bracket_count}/{total} references use bracket format (IEEE expects [n] format)",
                diagnostics={"bracket_count": bracket_count, "total": total},
            )]
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message=f"None of the {total} references use IEEE bracket format [n]",
            diagnostics={"total": total},
        )]


class IeeeSectionOrderRule(Rule):
    """IEEE-R02 — Sections follow expected IMRAD-like pattern."""

    def __init__(self):
        super().__init__("ieee-r02", Severity.WARNING)

    def check(self, doc: Document) -> list[RuleResult]:
        heading_texts = []
        for p in doc.paragraphs:
            if p.role == ParagraphRole.HEADING:
                heading_texts.append(p.text.strip().lower().rstrip(":"))

        if not heading_texts:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="No headings to check section order",
            )]

        expected = ["abstract", "introduction", "conclusion", "references"]
        found = []
        for exp in expected:
            for ht in heading_texts:
                if exp in ht:
                    found.append(exp)
                    break

        if len(found) >= 3:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Section order includes {len(found)}/{len(expected)} expected IEEE sections: {', '.join(found)}",
                diagnostics={"found_sections": found},
            )]
        if len(found) >= 2:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Section order includes {len(found)}/{len(expected)} expected sections",
                diagnostics={"found_sections": found},
            )]
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message=f"Only {len(found)}/{len(expected)} expected IEEE sections found ({', '.join(found) if found else 'none'})",
            diagnostics={"found_sections": found},
        )]


class IeeeCitationFormatRule(Rule):
    """IEEE-R03 — Citations use bracket format [n], not author-date."""

    def __init__(self):
        super().__init__("ieee-r03", Severity.WARNING)

    def check(self, doc: Document) -> list[RuleResult]:
        bracket_pattern = re.compile(r'\[(\d+)(?:,\s*\d+)*\]')
        ad_pattern = re.compile(r'\([A-Z][a-z]+(?:\s(?:&\s)?[A-Z][a-z]+)?,\s\d{4}[^)]*\)')

        bracket_count = 0
        ad_count = 0
        for p in doc.paragraphs:
            if p.role == ParagraphRole.BODY or p.role == ParagraphRole.HEADING:
                bracket_count += len(bracket_pattern.findall(p.text))
                ad_count += len(ad_pattern.findall(p.text))

        if bracket_count >= 2 and ad_count == 0:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Uses IEEE-style bracket citations [{bracket_count} occurrences], no author-date citations",
                diagnostics={"bracket_count": bracket_count, "author_date_count": ad_count},
            )]
        if bracket_count >= 2:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Uses bracket citations [{bracket_count} occurrences] (also found {ad_count} author-date citations)",
                diagnostics={"bracket_count": bracket_count, "author_date_count": ad_count},
            )]
        msg = f"Found {bracket_count} bracket citation(s)" if bracket_count > 0 else "No bracket citations found"
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message=f"{msg} (IEEE uses bracketed numbers [1], [2] for citations)",
            diagnostics={"bracket_count": bracket_count, "author_date_count": ad_count},
        )]


class IeeeFigureCaptionsRule(Rule):
    """IEEE-R04 — Figure captions follow 'Fig. n.' format."""

    def __init__(self):
        super().__init__("ieee-r04", Severity.INFO)

    def check(self, doc: Document) -> list[RuleResult]:
        fig_pattern = re.compile(r'Fig\.?\s*\d+', re.IGNORECASE)
        caption_count = sum(1 for p in doc.paragraphs if p.role == ParagraphRole.CAPTION)
        fig_captions = sum(1 for p in doc.paragraphs if p.role == ParagraphRole.CAPTION and fig_pattern.search(p.text))

        if caption_count == 0:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="No figure captions to check",
            )]
        if fig_captions == caption_count:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"All {caption_count} figure captions use 'Fig. n.' format",
                diagnostics={"caption_count": caption_count, "fig_captions": fig_captions},
            )]
        if fig_captions > 0:
            return [RuleResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"{fig_captions}/{caption_count} captions use IEEE-style 'Fig. n.' format",
                diagnostics={"caption_count": caption_count, "fig_captions": fig_captions},
            )]
        return [RuleResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message=f"{caption_count} caption(s) found but none use IEEE 'Fig. n.' format",
            diagnostics={"caption_count": caption_count},
        )]
