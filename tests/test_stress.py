"""Stress test runner — runs all documents through the pipeline and reports results."""
import json
import sys
import traceback
from pathlib import Path
from collections import Counter
from docstructure.parser.docx import DOCXParser
from docstructure.normalizer.normalize import normalize
from docstructure.features import extract_features
from docstructure.classifier.paragraph import classify_paragraphs
from docstructure.classifier.sections import build_regions
from docstructure.graph.resolver import resolve_relationships
from docstructure.output.json import to_json, serialize
from docstructure.validate.base import validate

STRESS_DIR = Path("/home/kunta/projects/tools/.samples/stress")
EXISTING_DIR = Path("/home/kunta/projects/tools/.samples")

STRESS_DOCS = {
    "apa_paper": STRESS_DIR / "apa_paper.docx",
    "business_report": STRESS_DIR / "business_report.docx",
    "resume": STRESS_DIR / "resume.docx",
    "thesis_chapter": STRESS_DIR / "thesis_chapter.docx",
    "weird_formatting": STRESS_DIR / "weird_formatting.docx",
    "large_document": STRESS_DIR / "large_document.docx",
}

EXISTING_DOCS = {
    "sample": EXISTING_DIR / "sample.docx",
    "samplelong": EXISTING_DIR / "samplelong.docx",
    "samplefin": EXISTING_DIR / "samplefin.docx",
    "pdf2docx": EXISTING_DIR / "sample.pdf2docx.tmp.docx",
}

FUZZ_DOCS = {
    "fuzz_empty_paragraphs": STRESS_DIR / "fuzz_empty_paragraphs.docx",
    "fuzz_nested_tables": STRESS_DIR / "fuzz_nested_tables.docx",
    "fuzz_hidden_text": STRESS_DIR / "fuzz_hidden_text.docx",
    "fuzz_mixed_numbering": STRESS_DIR / "fuzz_mixed_numbering.docx",
    "fuzz_multiple_references": STRESS_DIR / "fuzz_multiref.docx",
    "fuzz_no_headings": STRESS_DIR / "fuzz_no_headings.docx",
    "fuzz_only_tables": STRESS_DIR / "fuzz_only_tables.docx",
    "fuzz_corrupted": STRESS_DIR / "fuzz_corrupted.docx",
}


def run_pipeline(path: str):
    parser = DOCXParser()
    doc = parser.parse(path)
    num_paras = len(doc.paragraphs)
    num_nodes = len(doc.nodes)

    normalize(doc)
    extract_features(doc)
    classify_paragraphs(doc)
    build_regions(doc)
    resolve_relationships(doc)

    roles = Counter(b.role.value for b in doc.paragraphs if b.role)
    num_regions = len(doc.regions)
    num_edges = len(doc.edges)

    j = to_json(doc)
    json_size = len(j)

    # Validate
    validation = validate(doc)
    val_results = {r.rule_name: "PASS" if r.passed else "FAIL" for r in validation}
    val_ok = all(r.passed for r in validation)

    return {
        "paragraphs": num_paras,
        "nodes": num_nodes,
        "roles": dict(roles),
        "regions": num_regions,
        "edges": num_edges,
        "json_size": json_size,
        "validation": val_results,
        "validation_ok": val_ok,
        "doc": doc,
        "json": j,
    }


def run_test(name: str, path: Path, category: str):
    results = {"name": name, "path": str(path), "category": category, "status": "OK", "error": None}
    if not path.exists():
        results["status"] = "SKIP"
        results["error"] = "File not found"
        return results

    # Corrupted files are expected to fail at the parser level
    if "corrupted" in name:
        from docx.opc.exceptions import PackageNotFoundError
        try:
            run_pipeline(str(path))
            results["status"] = "UNEXPECTED_OK"
            results["error"] = "Corrupted file should have raised an error"
        except (PackageNotFoundError, Exception) as e:
            results["status"] = "OK"  # Expected failure
            results["error"] = f"Expected: {type(e).__name__}"
            print(f"  [OK] {name}: expected failure ({type(e).__name__})")
        return results

    try:
        info = run_pipeline(str(path))
        results.update(info)
        print(f"  [{results['status']}] {name}: {info['paragraphs']} paragraphs, "
              f"{info['json_size']} bytes JSON, "
              f"roles={dict(info['roles'])}, "
              f"val={'✓' if info['validation_ok'] else '✗'}")
    except Exception as e:
        results["status"] = "FAIL"
        results["error"] = f"{type(e).__name__}: {e}"
        results["traceback"] = traceback.format_exc()
        print(f"  [FAIL] {name}: {results['error']}")

    return results


def main():
    print("=" * 72)
    print("  DocStructure Phase 1 Stress Test Suite")
    print("=" * 72)

    all_results = []
    failures = 0

    # 1. Existing samples (baseline)
    print("\n── Existing samples ──")
    for name, path in EXISTING_DOCS.items():
        r = run_test(name, path, "existing")
        all_results.append(r)
        if r["status"] == "FAIL":
            failures += 1

    # 2. Stress tests
    print("\n── Stress tests ──")
    for name, path in STRESS_DOCS.items():
        r = run_test(name, path, "stress")
        all_results.append(r)
        if r["status"] == "FAIL":
            failures += 1

    # 3. Fuzz tests
    print("\n── Fuzz tests ──")
    for name, path in FUZZ_DOCS.items():
        r = run_test(name, path, "fuzz")
        all_results.append(r)
        if r["status"] == "FAIL":
            failures += 1

    # Summary
    print("\n" + "=" * 72)
    print("  Summary")
    print("=" * 72)
    total = len(all_results)
    ok = sum(1 for r in all_results if r["status"] == "OK")
    skipped = sum(1 for r in all_results if r["status"] == "SKIP")
    failed = sum(1 for r in all_results if r["status"] == "FAIL")
    print(f"  Total: {total}  OK: {ok}  Skipped: {skipped}  Failed: {failed}")
    if failed > 0:
        print("\n  Failures:")
        for r in all_results:
            if r["status"] == "FAIL":
                print(f"    - {r['name']}: {r['error']}")
        print("\n  Full tracebacks written below.")
        for r in all_results:
            if r.get("traceback"):
                print(f"\n  --- {r['name']} ---")
                print(r["traceback"])

    return failures


if __name__ == "__main__":
    sys.exit(main())
