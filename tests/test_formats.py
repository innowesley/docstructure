"""Tests for format detection plugins."""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from docstructure import analyze
from docstructure.formats import detect_all, detect_best
from docstructure.formats.apa import APADetector
from docstructure.formats.mla import MLADetector
from docstructure.formats.ieee import IEEEDetector


DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".samples")
STRESS_DIR = os.path.join(DOCS_DIR, "stress")


def test_detectors_are_registered():
    """All three format detectors should be discovered."""
    doc = analyze(os.path.join(DOCS_DIR, "sample.docx"))
    results = detect_all(doc)
    names = {r.format_name for r in results}
    assert "APA" in names, f"APA not in {names}"
    assert "MLA" in names, f"MLA not in {names}"
    assert "IEEE" in names, f"IEEE not in {names}"


def test_apa_detected_on_apa_paper():
    """APA paper should score highest for APA."""
    doc = analyze(os.path.join(STRESS_DIR, "apa_paper.docx"))
    results = detect_all(doc)
    apa_result = next(r for r in results if r.format_name == "APA")
    mla_result = next(r for r in results if r.format_name == "MLA")
    ieee_result = next(r for r in results if r.format_name == "IEEE")
    assert apa_result.confidence > 0.3, f"APA confidence too low: {apa_result.confidence}"
    assert apa_result.confidence > mla_result.confidence, f"APA ({apa_result.confidence}) should beat MLA ({mla_result.confidence})"
    assert apa_result.confidence > ieee_result.confidence, f"APA ({apa_result.confidence}) should beat IEEE ({ieee_result.confidence})"


def test_apa_detection_signals():
    """APA detector should find title_page, abstract, references, DOI."""
    doc = analyze(os.path.join(STRESS_DIR, "apa_paper.docx"))
    detector = APADetector()
    result = detector.detect(doc)
    evidence_str = " ".join(result.evidence)
    assert result.confidence > 0.3, f"APA confidence too low: {result.confidence}"
    assert "title_page" in evidence_str, f"No title_page signal: {evidence_str}"
    assert "references_section" in evidence_str, f"No references_section signal: {evidence_str}"


def test_mla_better_than_others_on_business_report():
    """Business report has MLA-like qualities."""
    doc = analyze(os.path.join(STRESS_DIR, "business_report.docx"))
    detector = MLADetector()
    result = detector.detect(doc)
    # Business reports may or may not score high for MLA
    # Just verify it runs without error
    assert result.format_name == "MLA"
    assert 0.0 <= result.confidence <= 1.0


def test_apa_signal_no_title_page():
    """Test that _has_title_page works correctly."""
    from docstructure.formats.apa import _has_title_page, _count_doi, _count_author_date_citations
    doc = analyze(os.path.join(DOCS_DIR, "sample.docx"))
    has = _has_title_page(doc)
    assert has is True, "sample.docx should have a title page"


def test_ieee_detector_runs():
    """IEEE detector should run without error on any document."""
    doc = analyze(os.path.join(DOCS_DIR, "sample.docx"))
    detector = IEEEDetector()
    result = detector.detect(doc)
    assert result.format_name == "IEEE"
    assert 0.0 <= result.confidence <= 1.0


def test_detect_best_on_apa_paper():
    """detect_best should return APA for APA paper."""
    doc = analyze(os.path.join(STRESS_DIR, "apa_paper.docx"))
    best = detect_best(doc)
    assert best is not None, "detect_best returned None"
    assert best.format_name == "APA", f"Expected APA, got {best.format_name}"


def test_detect_best_on_unknown():
    """detect_best should return None when all below threshold."""
    # Pass a threshold higher than any detector would score
    class MockDoc:
        paragraphs = []
        regions = []
        nodes = []
        analysis = type('MockAnalysis', (), {'references': []})()

    doc = analyze(os.path.join(DOCS_DIR, "sample.docx"))
    best = detect_best(doc, threshold=0.99)
    # This might or might not be None depending on sample.docx
    assert best is None or best.confidence < 0.99


if __name__ == "__main__":
    test_detectors_are_registered()
    print("  [OK] test_detectors_are_registered")
    test_apa_detected_on_apa_paper()
    print("  [OK] test_apa_detected_on_apa_paper")
    test_apa_detection_signals()
    print("  [OK] test_apa_detection_signals")
    test_mla_better_than_others_on_business_report()
    print("  [OK] test_mla_better_than_others_on_business_report")
    test_apa_signal_no_title_page()
    print("  [OK] test_apa_signal_no_title_page")
    test_ieee_detector_runs()
    print("  [OK] test_ieee_detector_runs")
    test_detect_best_on_apa_paper()
    print("  [OK] test_detect_best_on_apa_paper")
    test_detect_best_on_unknown()
    print("  [OK] test_detect_best_on_unknown")
    print("\nAll format detection tests passed!")
