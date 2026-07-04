# v0.2.0: docstructure Stabilization and Release

**Status:** Execution completed  
**Completed:** 2026-07-04  
**Target:** `tools/docstructure/` — packaging, API freeze, schema stability, performance, error handling, docs

---

## Overview

Pivot from feature-building to production quality. Prepare docstructure for a **v0.2.0** release on PyPI (or installable standalone).

### Deliverables

| # | Area | Description |
|---|------|-------------|
| 1 | **Packaging** | `pyproject.toml`, `src/` layout, editable install, dependency metadata, publish-ready |
| 2 | **Public API freeze** | `__all__`, top-level exports, deprecation warnings for lingering v1 patterns |
| 3 | **Schema stability** | v2 as default, `--schema v1|v2` CLI flag, v1 frozen as-is, deprecation notice |
| 4 | **Performance** | Synthetic document generator (deterministic), benchmark suite, baseline metrics |
| 5 | **Error handling** | Corrupted / password-protected / empty / edge-case input tests and hardening |
| 6 | **Documentation** | README.md: quick start, CLI, API, architecture, schema, validation, formats, examples, changelog |
| 7 | **CLI polish** | `--schema` flag, `--version`, help text consistency, exit codes |

---

## Existing Logic Analysis

### Current architecture

- `tools/docstructure/` is a flat Python package (keeps existing layout for v0.2.0)
- `__init__.py` exports `analyze`, `to_json`, `to_file`, `serialize`, `__version__=="0.1.0"`
- `__main__.py` has 4 subcommands: `analyze`, `graph`, `detect`, `validate`
- No `pyproject.toml`, `setup.py`, `setup.cfg`, `MANIFEST.in`, or `README.md`
- Dependencies in `tools/requirements.txt` (shared across all tools)
- Schema: `v1.json` (original) and `v2.json` (Phase 2, with format_detection + validation blocks)
- Pipeline runs 5 stages: normalize → features → classify → regions → resolve
- Format detection via `formats/` plugin system (APA, MLA, IEEE)
- Validation via `validate/` with format-specific rules (7 APA, 5 MLA, 4 IEEE)
- Tests: 5 golden, 16 stress, 8 format detection, 10 validation — all pass

### Hidden coupling

- `docstructure.parser.docx` imports `python-docx` directly — this is the sole hard dependency
- `acewriter` does NOT depend on `docstructure` (they share the old analyzer.py from Phase 1)
- `py` script (`/usr/local/bin/py`) manages venv at `tools/.venv/` — this is dev-only tooling
- `tools/AGENTS.md` references `docstructure` conventions — this needs updating for v0.2.0

### What assumes the current layout

| Consumer | What it assumes |
|----------|----------------|
| `py` launcher | Package is runnable as `py -m docstructure` from `tools/` root |
| `python -m docstructure` | CWD is `tools/`, package is on `PYTHONPATH` implicitly |
| `tests/golden_test.py` | `sys.path.insert(0, "../..")` to find `tools/docstructure` |
| `tests/test_stress.py` | Imports from `docstructure.*` with CWD as `tools/` |
| Golden files | Serialized with `docstructure.output.json.serialize()` — no changes needed |
| `docs/changelogs/` | Already using the changelog system |

### Decision: No `src/` migration for v0.2.0

Keep the existing flat layout. The `src/` migration is a packaging refactor that touches every import, test, CI config, and launcher. It adds risk without user-facing benefit. Reserved for a future v1.0 if still desirable.

New files added inside `tools/docstructure/`:
- `pyproject.toml`
- `README.md`
- `LICENSE`
- `benchmarks/` (new directory — NOT inside `tests/`)

---

## Potential Conflicts

| Conflict | Impact | Mitigation |
|----------|--------|------------|
| Editable install requires python-docx in new venv | python-docx must be installable | Already pure-Python, no system deps beyond what it declares |
| `pip install -e .` vs `py` launcher | `py` won't use the editable install automatically | Keep both working: `py -m docstructure` via launcher, `python -m docstructure` via editable install |
| Dynamic version from `__init__.py` | `pyproject.toml` reads `__version__` at build time | Uses `setuptools.dynamic` — standard approach |
| CLI `--schema` flag changes default output | Existing scripts calling `analyze` without `--schema` get v2 | v2 is already the current output; no change to default behavior |
| README duplicates AGENTS.md content | Drift | README is the public-facing doc; AGENTS.md is the AI-agent guide. Different audiences. |
| Exception hierarchy changes existing callers | New exception types may not be caught | `DocStructureError` base class allows catching all docstructure errors; existing callers using broad `except Exception` remain unaffected |

---

## Design

### 1. Packaging — `pyproject.toml` (keep existing layout)

No `src/` migration. Files remain at their current paths. Only add `pyproject.toml`, `README.md`, `LICENSE`.

```
docstructure/
├── __init__.py
├── __main__.py
├── pyproject.toml               ← NEW
├── README.md                    ← NEW
├── LICENSE                      ← NEW
├── benchmarks/                  ← NEW (separate from tests/)
├── ...
```

**`pyproject.toml`:**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "docstructure"
dynamic = ["version"]
description = "Document structure analysis engine — parse, classify, detect formats, validate"
requires-python = ">=3.10"
dependencies = [
    "python-docx>=1.1",
]
license = {text = "MIT"}
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Text Processing :: General",
]

[project.urls]
Homepage = "https://github.com/anomalyco/tools"
Documentation = "https://github.com/anomalyco/tools/tree/main/docstructure"

[tool.setuptools.package-data]
docstructure = ["output/schema/*.json"]

[tool.setuptools.dynamic]
version = {attr = "docstructure.__version__"}
```

**Version single-sourced** — `docstructure/__init__.py` defines `__version__ = "0.2.0"`; `pyproject.toml` reads it via `attr`. No duplicates.

**`requirements-dev.txt`:**

```txt
pytest>=8
ruff>=0.4
mypy>=1.10
```

**Editable install for monorepo dev:**

```bash
cd tools
pip install -e ./docstructure
```

`py` launcher also works unchanged (it runs from CWD with `tools/` implicitly on path).

### 2. Public API Freeze

Public surface is kept high-level. Internal things (`get_rules_for_format`, detector classes, pipeline stages) stay in submodules.

`__init__.py`:

```python
"""DocStructure — document structure analysis engine."""

from docstructure.pipeline import run_pipeline as analyze
from docstructure.parser.docx import DOCXParser
from docstructure.output.json import to_json, to_file, serialize
from docstructure.formats import detect_best as detect_format
from docstructure.validate.base import validate

__version__ = "0.2.0"
__all__ = [
    "analyze",
    "parse",
    "detect_format",
    "validate",
    "serialize",
    "to_json",
    "to_file",
    "__version__",
]

def parse(source: str) -> Document:
    """Parse a document file into a Document object (no analysis pipeline)."""
    from docstructure.parser.docx import DOCXParser
    parser = DOCXParser()
    return parser.parse(source)
```

**Public API Stability policy** — documented in README:

> **Guaranteed stable until v1.0:**
> `analyze()`, `parse()`, `detect_format()`, `validate()`, `serialize()`, `to_json()`, `to_file()`
>
> Everything else is internal and may change between minor versions.

### 3. Schema Stability

- **v1.json** — frozen, never modified except for critical fixes. Deprecated notice added as comment.
- **v2.json** — current default. All new output uses `schema: v2`.
- CLI gets `--schema v1|v2` flag on `analyze` subcommand.

### 4. Performance

**Synthetic document generator** — `benchmarks/generate.py`:

```python
# Deterministic (fixed seed) generator that produces .docx files at
# specified paragraph counts. Varies document structure to reflect
# real-world workloads: headings, body paragraphs, blank lines,
# references, numbered lists, bullet lists, nested lists, tables,
# mixed formatting (bold, italic, font sizes, alignment).
# Each document is reproducible for regression benchmarking.
```

**Benchmark suite** — `benchmarks/run.py`:

| Size | Paragraphs | Content type |
|------|-----------|--------------|
| XS | 10 | Mixed (headings + body + list) |
| S | 100 | Mixed |
| M | 500 | Mixed (existing `large_document.docx` also tested) |
| L | 1000 | Mixed |
| XL | 2500 | Mixed |
| XXL | 5000 | Mixed |

Metrics per document:

| Metric | Instrumentation |
|--------|-----------------|
| Wall time | `time.perf_counter()` per stage |
| CPU time | `time.process_time()` |
| Peak RSS | `tracemalloc` or `resource.getrusage()` |
| JSON size | `sys.getsizeof(json.dumps(...))` |
| Node count | `len(doc.nodes)` |
| Edge count | `len(doc.edges)` |

Benchmarks are **not** in `tests/` — they live in `benchmarks/` so `pytest` doesn't run them. CI runs them separately (nightly or on request).

Results written to `benchmarks/results/` as JSON for diffing across versions.

### 5. Error Handling

Separate into two categories — **unsupported** vs **invalid** — with different exception types.

#### Unsupported inputs (should raise `UnsupportedFormatError`)

| Input | Behavior |
|-------|----------|
| `.pdf` input | `UnsupportedFormatError: PDF parsing not yet supported. Try docx2pdf first.` |
| `.html`, `.md`, `.txt` | `UnsupportedFormatError: Only .docx files are supported in v0.2.0.` |
| Directory path | `UnsupportedFormatError: Expected a file, got a directory.` |

#### Invalid inputs (should raise `ParseError`)

| Input | Behavior |
|-------|----------|
| Corrupted `.docx` (truncated zip) | `ParseError: Corrupted file: ...` |
| Password-protected `.docx` | `ParseError: File is password-protected.` |
| Empty `.docx` (0 paragraphs) | Parse succeeds gracefully, 0 nodes |
| `.docx` with only images | Parse succeeds, 0 paragraphs, no crash |
| 100MB inflated docx | Memory-safe (streaming where possible) |
| Non-existent file | `FileNotFoundError` (standard Python, not wrapped) |
| Weird Unicode (RTL, combining chars, emoji) | Preserved in output |
| Invalid styles XML | Graceful fallback to defaults |
| Missing relationships | Skip silently with diagnostic |

Current parser (`docx.py`) already has some try/except handling. Gaps identified during testing.

#### Custom exceptions

```python
# docstructure/exceptions.py
class DocStructureError(Exception):
    """Base for all docstructure errors."""

class UnsupportedFormatError(DocStructureError):
    """Input format is not supported."""

class ParseError(DocStructureError):
    """File could not be parsed."""
```

### 6. Documentation

**README.md** structure:

```markdown
# DocStructure

Document structure analysis engine — parse .docx files, classify paragraphs, detect academic formats, and validate formatting rules.

## Quick Start

## Installation

## CLI Usage

## Python API

## Architecture

## Schema

## Validation

## Format Detection

## Examples

## Development

## Changelog
```

---

## Rollback Strategy

| Component | Rollback action |
|-----------|----------------|
| `pyproject.toml` | Delete it; project still runs as `py -m docstructure` |
| `src/` layout | Move files back to root; update all imports |
| README | Delete or revert |
| Benchmark generator | Delete `generate_benchmark_docs.py` and `test_benchmark.py` |
| Error handling changes | Revert individual parser changes |
| CLI `--schema` flag | Revert `__main__.py` changes |
| Schema deprecation notices | Revert comments in v1.json |

Each is independently reversible.

---

## Testing Strategy

| Test suite | What it validates |
|------------|------------------|
| Golden tests | No regression after changes |
| Stress tests | All stress documents parse correctly |
| Format detection tests | Detection unchanged |
| Validation tests | Validation rules unchanged |
| Error handling tests | Corrupted/malformed inputs produce clean errors |
| Packaging compatibility test | Fresh venv install works end-to-end |

### Packaging compatibility test (`tests/test_package.py`)

Creates a fresh virtual environment, installs the built package, and verifies:

```python
python -c "
import docstructure
doc = docstructure.analyze('sample.docx')
print(docstructure.serialize(doc)['docstructure_version'])
# → v2
"
```

### Benchmarks — separate from tests

`benchmarks/run.py` is **not** run by `pytest`. It's invoked explicitly:

```bash
py benchmarks/run.py             # full suite
py benchmarks/run.py --quick     # XS, S, M only
py benchmarks/run.py --compare   # diff against previous results
```

Results stored in `benchmarks/results/`.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `src/` layout breaks test imports | Medium | High | Run all tests immediately after move; fix path inserts |
| `pyproject.toml` dependency version conflicts | Low | Medium | Only `python-docx>=1.1` as dependency — stable |
| Schema file in wrong package-data location | Low | Medium | Verify `pip install -e .` includes `output/schema/*.json` |
| Benchmark flakiness (system load variance) | Medium | Low | Report median of 3 runs; document system state |
| Performance regression undetected | Low | Medium | Benchmark outputs are saved and diffable |
| README goes stale | Medium | Low | Add to CI: `doc-drift` check references it |

---

## Success Criteria

```bash
# 1. Standalone install works
pip install -e ./docstructure
python -c "from docstructure import analyze, parse, detect_format, validate; print('ok')"
# → ok

# 2. Version single-sourced
python -c "from docstructure import __version__; assert __version__ == '0.2.0'; print(__version__)"
# → 0.2.0

# 3. CLI works via pip install
python -m docstructure --help
# → Shows 4 subcommands

# 4. CLI still works via py launcher
py -m docstructure analyze .samples/sample.docx
# → JSON to stdout

# 5. --schema flag works
py -m docstructure analyze .samples/sample.docx --schema v1
# → Output uses v1 schema URL

# 6. All correctness tests pass
cd docstructure && py docstructure/tests/golden_test.py            # 5/5 pass
py -m docstructure.tests.test_stress                              # 16/16 pass
py docstructure/tests/test_formats.py                             # 8/8 pass
py docstructure/tests/test_validation.py                          # 10/10 pass

# 7. Benchmark runs
py docstructure/benchmarks/run.py --quick
# → Results printed, saved to benchmarks/results/
# Results: XS=0.18s S=0.50s M=2.19s (all under 3s)

# 8. Error handling — distinct exception types
# FileNotFoundError: nonexistent file
# UnsupportedFormatError: .pdf input
# ParseError: corrupted .docx

# 9. Packaging compatibility test
py -m docstructure.tests.test_package
# → Builds sdist, installs in fresh venv, smoke tests

# 10. Public API is clean
python -c "
from docstructure import analyze, parse, detect_format, validate, serialize, to_json, to_file
from docstructure import __all__
# → 8 items: analyze, parse, detect_format, validate, serialize, to_json, to_file, __version__
"

# 11. README renders correctly
# → Sections: Quick Start, Installation, CLI, API, Architecture, Schema, Validation, Formats, Examples

---

## Execution Log

### 2026-07-04 — v0.2.0 Release Preparation

- [x] Created `docstructure/pyproject.toml` — modern setuptools, static version, MIT license, SPDX expression
- [x] Created `docstructure/setup.py` — explicit package_dir mapping for flat-layout
- [x] Created `docstructure/exceptions.py` — DocStructureError, UnsupportedFormatError, ParseError
- [x] Created `docstructure/LICENSE` — MIT
- [x] Updated `docstructure/__init__.py` — frozen public API with `__all__`, `parse()` function, version via importlib.metadata
- [x] Updated `docstructure/__main__.py` — `--schema v1|v2` flag, `--version`, centralized error handling
- [x] Updated `docstructure/output/json.py` — `schema_version` param, v1/v2 schema URLs, omit v2-only fields for v1
- [x] Updated `docstructure/pipeline.py` — raise FileNotFoundError/UnsupportedFormatError/ParseError instead of sys.exit
- [x] Updated `docstructure/parser/docx.py` — ParseError for corrupted/password-protected files
- [x] Created `docstructure/README.md` — full docs: quick start, CLI, API, architecture, schema, validation, formats, dev
- [x] Created `benchmarks/generate.py` — deterministic synthetic doc generator (seed=42, varied structure)
- [x] Created `benchmarks/run.py` — wall/CPU time, peak RSS, JSON size, node/edge counts
- [x] Created `tests/test_package.py` — packaging compatibility test
- [x] Updated `tools/AGENTS.md` — v0.2.0 schema, CLI, subcommands, public API

### Verification

- [x] Golden tests: 5/5 pass
- [x] Stress tests: 16/16 pass
- [x] Format detection tests: 8/8 pass
- [x] Validation tests: 10/10 pass
- [x] `py -m docstructure --version` → `docstructure 0.2.0`
- [x] `py -m docstructure analyze .samples/sample.docx` → v2 JSON output
- [x] `py -m docstructure analyze .samples/sample.docx --schema v1` → v1 JSON output
- [x] `pip install docstructure/dist/docstructure-0.2.0.tar.gz` → installs cleanly
- [x] `py docstructure/benchmarks/generate.py` → 6 synthetic docs generated
- [x] `py docstructure/benchmarks/run.py --quick` → 3 benchmarks pass
- [x] Error handling: FileNotFoundError, UnsupportedFormatError, ParseError all distinct
- [x] Public API: `__all__` exports 8 items, no internal implementation details
