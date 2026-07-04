"""DocStructure CLI — analyze, detect, validate document structure."""

from __future__ import annotations

import argparse
import sys

from docstructure.pipeline import run_pipeline
from docstructure.output.json import to_json, to_file
from docstructure.validate.base import validate as run_validation
from docstructure.formats import detect_all, detect_best


# ── Format detection helpers ──


def _format_detection_text(detections) -> str:
    """Format detection results as human-readable text."""
    lines = []
    for d in detections:
        pct = round(d.confidence * 100)
        if d.evidence:
            ev = ", ".join(d.evidence)
            lines.append(f"  {d.format_name}: {pct}% ({ev})")
        else:
            lines.append(f"  {d.format_name}: {pct}%")
    return "\n".join(lines)


def _format_validation_results(vr) -> str:
    """Format validation results as human-readable text."""
    if not vr or not vr.rule_results:
        return "  No validation results"
    total = len(vr.rule_results)
    passed = sum(1 for r in vr.rule_results if r.passed)
    pct = round(vr.compliance_score * 100)
    lines = [f"  Format: {vr.format}", f"  Compliance: {pct}% ({passed}/{total} checks passed)"]
    for r in vr.rule_results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"    [{status}] {r.rule_id}: {r.message}")
    return "\n".join(lines)


# ── Command handlers ──


def cmd_analyze(args: argparse.Namespace) -> None:
    doc = run_pipeline(args.source, verbose=args.verbose)
    schema = args.schema if hasattr(args, 'schema') else "v2"
    if args.output:
        to_file(doc, args.output, schema_version=schema)
        if args.verbose:
            print(f"  Output: {args.output}")
    else:
        print(to_json(doc, schema_version=schema))
    if args.validate:
        results = run_validation(doc)
        errors = [r for r in results if not r.passed]
        if errors:
            print("\nValidation:", file=sys.stderr)
            for r in errors:
                print(f"  [{r.severity.value}] {r.rule_name}: {r.message}", file=sys.stderr)


def cmd_graph(args: argparse.Namespace) -> None:
    doc = run_pipeline(args.source, verbose=args.verbose)
    print(to_json(doc))


def cmd_detect(args: argparse.Namespace) -> None:
    import json as json_mod
    doc = run_pipeline(args.source, verbose=args.verbose)
    detections = detect_all(doc)
    best = detect_best(doc)

    if args.json:
        out = {
            "detections": [
                {"format": d.format_name, "confidence": d.confidence, "evidence": d.evidence}
                for d in detections
            ],
        }
        if best is not None:
            out["winner"] = best.format_name
            out["winner_confidence"] = best.confidence
        else:
            out["winner"] = None
            out["winner_confidence"] = 0.0
        print(json_mod.dumps(out, indent=2))
    else:
        print(_format_detection_text(detections))


def _build_format_detection_result(detections):
    from docstructure.core.analysis import FormatDetectionResult
    best = detections[0] if detections else None
    # Re-compute best since detect_best expects a doc
    best_conf = max(d.confidence for d in detections) if detections else 0.0
    best_name = next((d.format_name for d in detections if d.confidence == best_conf), None)
    return FormatDetectionResult(
        detections=[
            {"format": d.format_name, "confidence": d.confidence, "evidence": d.evidence}
            for d in detections
        ],
        winner=best_name if best_conf >= 0.3 else None,
        winner_confidence=best_conf if best_conf >= 0.3 else 0.0,
    )


def cmd_validate(args: argparse.Namespace) -> None:
    doc = run_pipeline(args.source, verbose=args.verbose)

    if args.format and args.format != "auto":
        # Explicit format
        fmt = args.format.upper()
        from docstructure.validate.rules import get_rules_for_format
        rules = get_rules_for_format(fmt)
        if not rules:
            print(f"No validation rules found for format: {fmt}", file=sys.stderr)
            sys.exit(1)
    else:
        # Auto-detect format first
        detections = detect_all(doc)
        winner = detect_best(doc)
        if winner is None:
            print("Could not detect document format. Use --format to specify.", file=sys.stderr)
            fmt = "UNKNOWN"
            rules = []
        else:
            fmt = winner.format_name
            from docstructure.validate.rules import get_rules_for_format
            rules = get_rules_for_format(fmt)

    doc.analysis.format_detection = _build_format_detection_result(
        detect_all(doc) if args.format == "auto" else []
    )

    if not rules:
        results = list(run_validation(doc))
        doc.analysis.validation = _build_validation_result(fmt, 0.0, results)
        print(_format_validation_results(doc.analysis.validation))
        if args.output:
            to_file(doc, args.output)
        sys.exit(1 if any(not getattr(r, 'passed', False) for r in results) else 0)
        return

    # Run format-specific rules
    from docstructure.validate.base import Rule
    rule_results = []
    for rule in rules:
        rule_results.extend(rule.check(doc))

    passed_count = sum(1 for r in rule_results if r.passed)
    total_count = len(rule_results)
    compliance = passed_count / total_count if total_count > 0 else 0.0

    from docstructure.core.analysis import ValidationResult, ValidationRuleResult
    vrr = [
        ValidationRuleResult(
            rule_id=r.rule_name,
            passed=r.passed,
            severity=r.severity.value if hasattr(r.severity, 'value') else str(r.severity),
            message=r.message,
        )
        for r in rule_results
    ]
    doc.analysis.validation = ValidationResult(
        format=fmt,
        compliance_score=compliance,
        rule_results=vrr,
    )

    print(_format_validation_results(doc.analysis.validation))

    if args.output:
        to_file(doc, args.output)

    failed = sum(1 for r in rule_results if not r.passed)
    sys.exit(1 if failed > 0 else 0)


def _build_validation_result(fmt, score, results):
    from docstructure.core.analysis import ValidationResult, ValidationRuleResult
    vrr = [
        ValidationRuleResult(
            rule_id=r.rule_name,
            passed=r.passed,
            severity=r.severity.value if hasattr(r.severity, 'value') else str(r.severity),
            message=r.message,
        )
        for r in results
    ]
    return ValidationResult(format=fmt, compliance_score=score, rule_results=vrr)


# ── Argument parser ──


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DocStructure — document structure analysis engine",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--version", action="version", version=f"docstructure {__import__('docstructure').__version__}")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    analyze_p = sub.add_parser("analyze", help="Analyze document structure")
    analyze_p.add_argument("source", help="Path to .docx file")
    analyze_p.add_argument("--output", "-o", help="Output JSON file path")
    analyze_p.add_argument("--validate", action="store_true", help="Run validation after analysis")
    analyze_p.add_argument("--schema", choices=["v1", "v2"], default="v2", help="Output schema version (default: v2)")
    analyze_p.set_defaults(func=cmd_analyze)

    graph_p = sub.add_parser("graph", help="Output document graph")
    graph_p.add_argument("source", help="Path to .docx file")
    graph_p.set_defaults(func=cmd_graph)

    detect_p = sub.add_parser("detect", help="Detect document format (APA/MLA/IEEE)")
    detect_p.add_argument("source", help="Path to .docx file")
    detect_p.add_argument("--json", action="store_true", help="JSON output")
    detect_p.set_defaults(func=cmd_detect)

    validate_p = sub.add_parser("validate", help="Validate document structure against a format")
    validate_p.add_argument("source", help="Path to .docx file")
    validate_p.add_argument("--format", "-f", choices=["apa", "mla", "ieee", "auto"], default="auto", help="Format to validate against")
    validate_p.add_argument("--output", "-o", help="Output validation JSON file path")
    validate_p.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ImportError as e:
        print(f"Error: Missing dependency: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
