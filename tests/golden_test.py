"""Golden test suite — regression tests for DocStructure Phase 1.

Each test parses a document and compares the JSON output against a saved
golden file. Tests fail if the output diverges (unless the model changed
intentionally, in which case the golden files are regenerated).

Usage:
    py golden_test.py                # run all tests
    py golden_test.py --update       # regenerate golden files
    py golden_test.py <name>         # run single test
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from docstructure import analyze

GOLDEN_DIR = Path(__file__).parent / "golden"
DOCS_DIR = Path("/home/kunta/projects/tools/.samples")

GOLDEN_TESTS = {
    "sample": DOCS_DIR / "sample.docx",
    "samplelong": DOCS_DIR / "samplelong.docx",
    "apa_paper": DOCS_DIR / "stress/apa_paper.docx",
    "business_report": DOCS_DIR / "stress/business_report.docx",
    "resume": DOCS_DIR / "stress/resume.docx",
}

# Non-deterministic fields that change on every run
SKIP_FIELDS: set[str] = {
    "document.id",
    "document.created_at",
}


def generate_golden(name: str, path: Path) -> dict:
    doc = analyze(str(path))
    from docstructure.output.json import serialize
    return serialize(doc)


def save_golden(name: str, data: dict) -> Path:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    path = GOLDEN_DIR / f"{name}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def load_golden(name: str) -> dict:
    path = GOLDEN_DIR / f"{name}.json"
    with open(path) as f:
        return json.load(f)


def diff_dicts(got: dict, expected: dict, path: str = "") -> list[str]:
    """Recursively diff two dicts, skipping known non-deterministic fields."""
    if path in SKIP_FIELDS:
        return []

    diffs: list[str] = []
    all_keys = set(got.keys()) | set(expected.keys())
    for k in sorted(all_keys):
        kpath = f"{path}.{k}" if path else k
        if kpath in SKIP_FIELDS:
            continue
        if k not in got:
            diffs.append(f"{kpath}: missing in output")
            continue
        if k not in expected:
            diffs.append(f"{kpath}: unexpected key in output")
            continue

        gv = got[k]
        ev = expected[k]

        if isinstance(gv, dict) and isinstance(ev, dict):
            diffs.extend(diff_dicts(gv, ev, kpath))
        elif isinstance(gv, list) and isinstance(ev, list):
            if len(gv) != len(ev):
                diffs.append(f"{kpath}: length mismatch ({len(gv)} vs {len(ev)})")
            else:
                for i, (gi, ei) in enumerate(zip(gv, ev)):
                    if isinstance(gi, dict) and isinstance(ei, dict):
                        diffs.extend(diff_dicts(gi, ei, f"{kpath}[{i}]"))
                    elif gi != ei:
                        diffs.append(f"{kpath}[{i}]: '{str(gi)[:40]}' != '{str(ei)[:40]}'")
        elif gv != ev:
            diffs.append(f"{kpath}: '{str(gv)[:60]}' != '{str(ev)[:60]}'")

    return diffs


def test_single(name: str, path: Path, update: bool = False) -> list[str]:
    print(f"  {name}... ", end="", flush=True)
    try:
        got = generate_golden(name, path)
    except Exception as e:
        print(f"PARSE ERROR: {e}")
        return [f"Parse error: {e}"]

    if update:
        saved = save_golden(name, got)
        print(f"golden updated ({saved})")
        return []

    expected = load_golden(name)
    diffs = diff_dicts(got, expected)
    if not diffs:
        print("PASS")
    else:
        print("FAIL")
        for d in diffs[:10]:
            print(f"    {d}")
    return diffs


def main():
    update = "--update" in sys.argv or "-u" in sys.argv

    names = [a for a in sys.argv[1:] if not a.startswith("-")]
    tests = {}
    if names:
        for n in names:
            if n in GOLDEN_TESTS:
                tests[n] = GOLDEN_TESTS[n]
            else:
                print(f"Unknown test '{n}'. Available: {list(GOLDEN_TESTS.keys())}")
                return 1
    else:
        tests = dict(GOLDEN_TESTS)

    total = 0
    failed = 0
    for name, path in tests.items():
        diffs = test_single(name, path, update=update)
        if diffs:
            failed += 1
        total += 1

    print(f"\n  {total} tests, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
