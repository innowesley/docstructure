"""DocStructure CLI — analyze document structure."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from docstructure.core.document import Document
from docstructure.normalizer.normalize import normalize
from docstructure.features import extract_features
from docstructure.classifier.paragraph import classify_paragraphs
from docstructure.classifier.sections import build_regions
from docstructure.graph.resolver import resolve_relationships
from docstructure.output.json import to_json, to_file
from docstructure.validate.base import validate, RuleResult


def _resolve_docx(source: str | Path) -> Document:
    """Parse a .docx file using the DOCX parser."""
    from docstructure.parser.docx import DOCXParser
    parser = DOCXParser()
    return parser.parse(str(source))


PARSERS = {
    ".docx": _resolve_docx,
    # Future: ".pdf", ".html", ".md"
}


def run_pipeline(source: str, verbose: bool = False) -> Document:
    """Full analysis pipeline."""
    path = Path(source)
    ext = path.suffix.lower()

    parser_fn = PARSERS.get(ext)
    if parser_fn is None:
        print(f"Unsupported file type: {ext}", file=sys.stderr)
        sys.exit(1)

    if not path.exists():
        print(f"File not found: {source}", file=sys.stderr)
        sys.exit(1)

    try:
        doc = parser_fn(source)
    except Exception as e:
        print(f"Error: Cannot parse '{source}': {e}", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"  Parsed: {len(doc.paragraphs)} paragraphs, {len(doc.nodes)} total nodes")

    normalize(doc)
    if verbose:
        print(f"  Normalized")

    extract_features(doc)
    if verbose:
        print(f"  Features extracted")

    classify_paragraphs(doc)
    if verbose:
        print(f"  Paragraphs classified")

    build_regions(doc)
    if verbose:
        print(f"  Regions built")

    resolve_relationships(doc)
    if verbose:
        print(f"  Relationships resolved")

    return doc


def cmd_analyze(args: argparse.Namespace) -> None:
    """Analyze a document and output structure JSON."""
    doc = run_pipeline(args.source, verbose=args.verbose)

    if args.output:
        to_file(doc, args.output)
        if args.verbose:
            print(f"  Output: {args.output}")
    else:
        print(to_json(doc))

    if args.validate:
        results = validate(doc)
        errors = [r for r in results if not r.passed]
        if errors:
            print("\nValidation:", file=sys.stderr)
            for r in errors:
                print(f"  [{r.severity.value}] {r.rule_name}: {r.message}", file=sys.stderr)
            if args.verbose:
                print(f"  {len(errors)} rule(s) failed", file=sys.stderr)


def cmd_graph(args: argparse.Namespace) -> None:
    """Output the document graph (nodes + edges)."""
    doc = run_pipeline(args.source, verbose=args.verbose)
    print(to_json(doc))


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate a document against structural rules."""
    doc = run_pipeline(args.source, verbose=args.verbose)
    results = validate(doc)
    passed = 0
    failed = 0
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        if r.passed:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] {r.rule_name}: {r.message}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed > 0 else 0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DocStructure — document structure analysis engine",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # analyze
    analyze_p = sub.add_parser("analyze", help="Analyze document structure")
    analyze_p.add_argument("source", help="Path to .docx file")
    analyze_p.add_argument("--output", "-o", help="Output JSON file path")
    analyze_p.add_argument("--validate", action="store_true", help="Run validation after analysis")
    analyze_p.set_defaults(func=cmd_analyze)

    # graph
    graph_p = sub.add_parser("graph", help="Output document graph")
    graph_p.add_argument("source", help="Path to .docx file")
    graph_p.set_defaults(func=cmd_graph)

    # validate
    validate_p = sub.add_parser("validate", help="Validate document structure")
    validate_p.add_argument("source", help="Path to .docx file")
    validate_p.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
