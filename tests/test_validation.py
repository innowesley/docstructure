"""Tests for format-specific validation rules."""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from docstructure import analyze
from docstructure.validate.rules.apa_rules import (
    ApaRunningHeadRule,
    ApaAbstractRule,
    ApaReferencesRule,
    ApaDoiRule,
    ApaHeadingOrderRule,
    ApaFontRule,
    ApaAuthorDateRule,
)
from docstructure.validate.rules.mla_rules import (
    MlaNoTitlePageRule,
    MlaHeaderRule,
    MlaWorksCitedRule,
    MlaAuthorPageCitationsRule,
    MlaHangingIndentRule,
)
from docstructure.validate.rules.ieee_rules import (
    IeeeNumberedReferencesRule,
    IeeeSectionOrderRule,
    IeeeCitationFormatRule,
    IeeeFigureCaptionsRule,
)
from docstructure.validate.rules import get_rules_for_format


DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".samples")
STRESS_DIR = os.path.join(DOCS_DIR, "stress")


def test_apa_rules_registered():
    """APA should have 7 rules registered."""
    rules = get_rules_for_format("APA")
    assert len(rules) == 7, f"Expected 7 APA rules, got {len(rules)}"
    names = [r.name for r in rules]
    assert "apa-7.01" in names
    assert "apa-7.02" in names
    assert "apa-7.03" in names
    assert "apa-7.04" in names
    assert "apa-7.05" in names
    assert "apa-7.06" in names
    assert "apa-7.08" in names


def test_mla_rules_registered():
    """MLA should have 5 rules registered."""
    rules = get_rules_for_format("MLA")
    assert len(rules) == 5, f"Expected 5 MLA rules, got {len(rules)}"
    names = [r.name for r in rules]
    assert "mla-9.01" in names
    assert "mla-9.02" in names
    assert "mla-9.03" in names
    assert "mla-9.04" in names
    assert "mla-9.05" in names


def test_ieee_rules_registered():
    """IEEE should have 4 rules registered."""
    rules = get_rules_for_format("IEEE")
    assert len(rules) == 4, f"Expected 4 IEEE rules, got {len(rules)}"
    names = [r.name for r in rules]
    assert "ieee-r01" in names
    assert "ieee-r02" in names
    assert "ieee-r03" in names
    assert "ieee-r04" in names


def test_apa_references_rule():
    """ApaReferencesRule should find references on sample.docx."""
    doc = analyze(os.path.join(DOCS_DIR, "sample.docx"))
    rule = ApaReferencesRule()
    results = rule.check(doc)
    assert len(results) == 1
    assert results[0].passed, f"Expected references to be found: {results[0].message}"
    assert results[0].diagnostics.get("reference_count", 0) >= 5


def test_apa_heading_order_rule():
    """ApaHeadingOrderRule should pass on sample.docx."""
    doc = analyze(os.path.join(DOCS_DIR, "sample.docx"))
    rule = ApaHeadingOrderRule()
    results = rule.check(doc)
    assert len(results) == 1
    assert results[0].passed, f"Heading order check failed: {results[0].message}"


def test_apa_running_head_rule_on_sample():
    """ApaRunningHeadRule — sample.docx may not have running head."""
    doc = analyze(os.path.join(DOCS_DIR, "sample.docx"))
    rule = ApaRunningHeadRule()
    results = rule.check(doc)
    assert len(results) == 1


def test_mla_works_cited_rule():
    """MlaWorksCitedRule should find references on sample.docx."""
    doc = analyze(os.path.join(DOCS_DIR, "sample.docx"))
    rule = MlaWorksCitedRule()
    results = rule.check(doc)
    assert len(results) == 1


def test_ieee_numbered_references():
    """IeeeNumberedReferencesRule on sample.docx (APA refs, not IEEE)."""
    doc = analyze(os.path.join(DOCS_DIR, "sample.docx"))
    rule = IeeeNumberedReferencesRule()
    results = rule.check(doc)
    # sample.docx has APA references, not IEEE numbered refs
    assert len(results) == 1
    assert not results[0].passed


def test_empty_rules_for_unknown_format():
    """get_rules_for_format should return empty for unknown format."""
    rules = get_rules_for_format("UNKNOWN")
    assert rules == []


def test_mla_header_rule_on_sample():
    """MlaHeaderRule on sample.docx (APA paper)."""
    doc = analyze(os.path.join(DOCS_DIR, "sample.docx"))
    rule = MlaHeaderRule()
    results = rule.check(doc)
    assert len(results) == 1


if __name__ == "__main__":
    test_apa_rules_registered()
    print("  [OK] test_apa_rules_registered")
    test_mla_rules_registered()
    print("  [OK] test_mla_rules_registered")
    test_ieee_rules_registered()
    print("  [OK] test_ieee_rules_registered")
    test_apa_references_rule()
    print("  [OK] test_apa_references_rule")
    test_apa_heading_order_rule()
    print("  [OK] test_apa_heading_order_rule")
    test_apa_running_head_rule_on_sample()
    print("  [OK] test_apa_running_head_rule_on_sample")
    test_mla_works_cited_rule()
    print("  [OK] test_mla_works_cited_rule")
    test_ieee_numbered_references()
    print("  [OK] test_ieee_numbered_references")
    test_empty_rules_for_unknown_format()
    print("  [OK] test_empty_rules_for_unknown_format")
    test_mla_header_rule_on_sample()
    print("  [OK] test_mla_header_rule_on_sample")
    print("\nAll validation rule tests passed!")
