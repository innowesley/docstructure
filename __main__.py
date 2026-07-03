"""DocStructure CLI — analyze document structure."""

from __future__ import annotations

import argparse
import sys

from docstructure.pipeline import run_pipeline
from docstructure.output.json import to_json, to_file
from docstructure.validate.base import validate


def cmd_analyze(args: argparse.Namespace) -> None:
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


def cmd_graph(args: argparse.Namespace) -> None:
    doc = run_pipeline(args.source, verbose=args.verbose)
    print(to_json(doc))


def cmd_validate(args: argparse.Namespace) -> None:
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

    if args.output:
        import json
        from datetime import datetime, timezone
        out = {
            "document": {"source": args.source},
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "results": [
                {
                    "rule_name": r.rule_name,
                    "passed": r.passed,
                    "severity": r.severity.value,
                    "message": r.message,
                }
                for r in results
            ],
            "summary": {"passed": passed, "failed": failed},
        }
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2)
        if args.verbose:
            print(f"  Output: {args.output}")

    sys.exit(1 if failed > 0 else 0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DocStructure — document structure analysis engine",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    analyze_p = sub.add_parser("analyze", help="Analyze document structure")
    analyze_p.add_argument("source", help="Path to .docx file")
    analyze_p.add_argument("--output", "-o", help="Output JSON file path")
    analyze_p.add_argument("--validate", action="store_true", help="Run validation after analysis")
    analyze_p.set_defaults(func=cmd_analyze)

    graph_p = sub.add_parser("graph", help="Output document graph")
    graph_p.add_argument("source", help="Path to .docx file")
    graph_p.set_defaults(func=cmd_graph)

    validate_p = sub.add_parser("validate", help="Validate document structure")
    validate_p.add_argument("source", help="Path to .docx file")
    validate_p.add_argument("--output", "-o", help="Output validation JSON file path")
    validate_p.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
