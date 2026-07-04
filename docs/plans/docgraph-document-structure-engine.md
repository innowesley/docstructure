# DocGraph — Document Structure Analysis Engine

**Status:** Draft  
**Target:** `tools/docgraph/` — new standalone tool  
**Relationship to acewriter:** Separate tool; acewriter will depend on it (Phase 3)

---

## Vision

Build a **semantic document structure engine** — not an APA parser, not a DOCX parser.

Transform unstructured documents into a rich, typed **Document AST** with confidence scores. Everything else (APA validation, humanization hints, table extraction, TOC generation, accessibility checking) is a plugin built on top of the AST.

---

## Ecosystem Gap — Why This Doesn't Exist Yet

After thorough research: there is **no mature open-source library** (Python or npm) that can reliably detect document structure, infer format, and validate compliance. Here's what exists and where each falls short:

| Library | Good for | Missing |
|---------|----------|---------|
| `python-docx` | Reading DOCX styles, paragraphs, tables | No document understanding |
| `PyMuPDF` / `pdfplumber` | PDF text + layout extraction | No academic structure detection |
| `GROBID` | Scientific papers (PDF) | Published articles only, not student papers or DOCX |
| `dedoc` | Some document structure | General documents, not format-aware |
| `docx2python` / `mammoth` | Text/HTML extraction | No semantic analysis at all |
| `citeproc-py` / `bibtexparser` | Citation formatting | Format references, don't analyze documents |
| `LanguageTool` / `Vale` | Writing style checks | Don't detect document regions or academic formats |

**The gap:** Combining wordprocessing formats + typography + layout analysis + classification + rule engines + academic style guides into one coherent system. Existing projects solve only one piece.

**This is also the opportunity.** A high-quality, extensible document structure engine with format detection and validation doesn't have a well-established equivalent in either Python or npm ecosystems.

---

## Platform Strategy — Python First, Multi-Language Output from Day One

### What we build first

```
Phase 1         Python library (pip install docgraph)
Phase 2         CLI (py -m docgraph)
Phase 3         JSON API / REST endpoint
Phase 4         npm wrapper (calls Python core)
Phase 5         VS Code extension
Phase 6         Browser/WASM (optional)
```

### Language-neutral JSON from day one

The **JSON output format is the contract**. Every language receives the same structure:

```json
{
  "metadata": {
    "source": "paper.docx",
    "paragraph_count": 142,
    "page_count": 12
  },
  "format": {
    "detected": "APA",
    "confidence": 0.94,
    "alternatives": [
      {"name": "MLA", "confidence": 0.12},
      {"name": "IEEE", "confidence": 0.08}
    ]
  },
  "regions": [
    {"type": "front_matter", "start": 0, "end": 7, "confidence": 95},
    {"type": "body", "start": 8, "end": 128, "confidence": 98},
    {"type": "back_matter", "start": 129, "end": 141, "confidence": 96}
  ],
  "paragraphs": [
    {
      "index": 12,
      "class": "body",
      "role": "body",
      "confidence": 0.99,
      "text": "Artificial intelligence has transformed...",
      "features": {
        "word_count": 24,
        "sentence_count": 2,
        "font_size": 12.0,
        "bold": false,
        "centered": false
      },
      "scores": {
        "body": 12,
        "heading": 1,
        "title": 0,
        "metadata": 0,
        "reference": 0
      }
    }
  ],
  "headings": [...],
  "tables": [...]
}
```

Python, JavaScript, CLI, and HTTP API all produce the **same JSON**. This means:
- npm package can just shell out to the CLI
- VS Code extension can use the CLI or HTTP API
- Web app can use the HTTP API
- Only the Python core needs to be maintained

### What to build on (don't reinvent low-level parsing)

| Task | Library | Why |
|------|---------|-----|
| DOCX reading | `python-docx` | Mature, stable, handles styles/runs/tables |
| PDF reading | `PyMuPDF` (fitz) | Best layout extraction + coordinates |
| Fuzzy matching | `rapidfuzz` | Matching section names, author names |
| XML parsing | `lxml` | ODT, RTF intermediate formats |
| CLI output | `rich` | Already in the toolchain |
| Pattern matching | `regex` (stdlib) | Citation patterns, reference formats |

The innovation is the **semantic layer** above these libraries — the classification engine, state machine, format detectors, and validators. That's where docgraph provides unique value.

---

## Architecture

```
PDF  DOCX  ODT  RTF  HTML  MD  TXT
          │
          ▼
   Document Parser (per-format)
          │
          ▼
   Layout + Style Model
          │
          ▼
   Feature Extraction (lexical, typography, spacing, numbering)
          │
          ▼
   Paragraph Classification (confidence-based score vector)
          │
          ▼
   Structure State Machine (FRONT → BODY → BACK → APPENDIX)
          │
          ▼
   Document Graph (typed AST with confidence)
          │
          ├──▶ JSON exporter
          ├──▶ Format Detection (APA:91%, MLA:12%, …)
          ├──▶ Format Validation (compliance score + errors)
          ├──▶ HTML/MD exporters
          └──▶ acewriter integration
```

### Two separate problems

| Stage | Question | Output |
|-------|----------|--------|
| **Format detection** | "What is this document *trying* to be?" | `[FormatScore(APA, 91%), FormatScore(MLA, 12%)]` |
| **Format validation** | "How well does it conform to that format?" | `ValidationResult(score=67, errors=[…], warnings=[…])` |

Never booleans. Always confidence + explanation.

---

## Phase Plan

### Phase 1 — Core Engine + DOCX (this build)

**Goal:** Parse DOCX → document graph → JSON. CLI working. Acewriter-compatible output.

**What we build:**

| Layer | Files | Source |
|-------|-------|--------|
| Models | `model/paragraph.py`, `model/section.py`, `model/block.py`, `model/document.py`, `model/run.py`, `model/table.py` | Extracted/refactored from acewriter `analyzer.py` |
| Parser | `parser/__init__.py` (base), `parser/docx.py` | Extracted from acewriter `analyzer.py:_build_paragraph_info()` + `_detect_headings()` |
| Features | `features/lexical.py`, `features/typography.py`, `features/spacing.py`, `features/numbering.py` | Extracted from acewriter `_extract_features()` |
| Classifier | `classifier/paragraph.py` | Extracted from acewriter `_compute_scores()` + `_classify_paragraphs()` |
| State machine | `state_machine/document.py` | Extracted from acewriter `_state_machine()` + `_assemble_regions()` |
| Detectors | `detectors/cover.py`, `detectors/headings.py`, `detectors/references.py`, `detectors/abstract.py`, `detectors/toc.py` | Extracted from acewriter scoring functions + constants |
| Exporters | `exporters/json.py` | New |
| CLI | `__init__.py`, `__main__.py` | New |

**Data models (simplified from acewriter, generalized):**

```python
# model/paragraph.py
@dataclass
class Paragraph:
    index: int
    text: str
    style_name: str
    block_type: BlockType
    role: ParagraphRole
    confidence: float
    # Style
    centered: bool
    bold: bool
    font_name: str
    font_size: float | None
    # Metrics
    word_count: int
    char_count: int
    sentence_count: int
    has_page_break: bool
    # Features (computed once)
    features: ParagraphFeatures | None = None
    # Classification scores (full vector)
    scores: ClassificationScores | None = None
    # Positional (for PDF/HTML)
    page: int | None = None
    bbox: tuple[float,float,float,float] | None = None

# model/block.py
class BlockType(Enum):
    BODY_TEXT, HEADING, TITLE, SUBTITLE, METADATA, CAPTION,
    CODE, TABLE, EQUATION, LIST, BLANK, UNKNOWN,
    ABSTRACT, TOC, REFERENCE, FOOTNOTE, HEADER, FOOTER  # NEW

# model/section.py  
class RegionType(Enum):
    FRONT_MATTER, BODY, BACK_MATTER, APPENDIX

@dataclass
class Region:
    type: RegionType
    start: int
    end: int
    confidence: int
    signals: list[Signal]
    children: list[Region]

# model/document.py
@dataclass
class DocumentGraph:
    metadata: dict
    paragraphs: list[Paragraph]
    headings: list[Heading]
    regions: list[Region]
    tables: list[Table]
    body_range: tuple[int, int]
```

**Pipeline (`parser/docx.py` → `DocumentGraph`):**

```
docx_document
    │
    ▼
extract_paragraphs()        → Paragraph[]
    │
    ▼
detect_headings()            → Heading[]
    │
    ▼
extract_features()           → ParagraphFeatures[]
    │
    ▼  
classify_paragraphs()        → block_type + confidence assigned
    │
    ▼
state_machine()              → role (FRONT/BODY/BACK) assigned
    │
    ▼
assemble_regions()           → Region[]
    │
    ▼
DocumentGraph
```

**API:**

```python
import docgraph

# Primary entry point
doc = docgraph.open("paper.docx")

# Access
doc.paragraphs        # → list[Paragraph]
doc.headings          # → list[Heading]
doc.regions           # → list[Region]
doc.tables            # → list[Table]
doc.body_range        # → (start, end)
doc.structure         # → {front_matter, body, back_matter}

# Export (language-neutral JSON)
doc.to_json()         # → dict (serializable, language-neutral)
doc.to_json(indent=2) # → dict (pretty-printed for CLI output)
```

**Design principle: `to_json()` output IS the API contract.** The JSON dict uses the same field names and structure that the npm wrapper, REST API, and CLI will produce. No Python-specific types leak into the JSON.

**CLI:**

```bash
py -m docgraph paper.docx                       # Structure summary (stderr)
py -m docgraph paper.docx --json                # Full AST JSON (stdout)
py -m docgraph paper.docx --debug               # Detailed debug output
py -m docgraph paper.docx --pretty              # Pretty-printed JSON
py -m docgraph paper.docx -o output.json        # Save to file
```

**Files to create** (new tool skeleton):

```
tools/docgraph/
├── __init__.py
├── __main__.py                 # CLI entry point
├── lib/
│   ├── __init__.py
│   ├── model/
│   │   ├── __init__.py          # Re-export all model types
│   │   ├── paragraph.py         # Paragraph, ParagraphFeatures, ParagraphRole, ClassificationScores
│   │   ├── section.py           # Region, RegionType
│   │   ├── block.py             # BlockType
│   │   ├── document.py          # DocumentGraph
│   │   ├── table.py             # Table, TableRow, TableCell
│   │   ├── run.py               # Run (inline formatting)
│   │   └── base.py              # Signal, Heading
│   ├── parser/
│   │   ├── __init__.py          # Parser base class / registry
│   │   ├── docx.py              # DOCX parser (extracted from acewriter)
│   │   └── ...                  # md.py, pdf.py, etc. in later phases
│   ├── features/
│   │   ├── __init__.py
│   │   ├── lexical.py           # Word count, sentence count, vocabulary diversity
│   │   ├── typography.py        # Font name, size, bold, italic, mono, case
│   │   ├── spacing.py           # Indentation, blank lines before/after
│   │   └── numbering.py         # Outline level, bullet detection
│   ├── classifier/
│   │   ├── __init__.py
│   │   └── paragraph.py         # Score functions + classification
│   ├── state_machine/
│   │   ├── __init__.py
│   │   └── document.py          # FRONT→BODY→BACK state machine
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── cover.py             # Cover page detection (from acewriter COVER_KEYWORDS)
│   │   ├── headings.py          # Heading detection
│   │   ├── references.py        # Reference section detection
│   │   ├── abstract.py          # Abstract detection
│   │   └── toc.py               # Table of contents detection
│   └── exporters/
│       ├── __init__.py
│       └── json.py              # JSON AST export
```

**Dependencies (add to `tools/requirements.txt`):**
- `python-docx` (already present)
- `rich` (for CLI formatting, already present)

**No new dependencies for Phase 1.**

---

### Phase 2 — Format Detection & Validation

**Goal:** Detect what format a document is *trying* to be, then validate compliance.

**What we build:**

| Component | Description |
|-----------|-------------|
| `detectors/formats/base.py` | Abstract `FormatDetector` + `FormatValidator` |
| `detectors/formats/apa.py` | APA format detector + validator |
| `detectors/formats/mla.py` | MLA format detector + validator |
| `exporters/html.py` | HTML report of validation results |

**Format detection pipeline:**

```
DocumentGraph
    │
    ▼
FormatDetector.detect(graph)
    │
    ├── APA: 91% (cover + abstract + references + heading hierarchy + DOI pattern)
    ├── MLA: 12% (no cover, Works Cited, parenthetical author-page)
    ├── IEEE: 8% (numbered references, specific heading style)
    └── Chicago: 3%
    │
    ▼
FormatValidator(detected_format).validate(graph)
    │
    ▼
ValidationResult(score=67, passed=False,
    errors=[...], warnings=[...])
```

**Example validator output:**

```python
ValidationResult(
    format="APA",
    detection_confidence=0.91,
    compliance_score=0.67,
    checks=[
        Check("References page exists", passed=True),
        Check("APA citations detected", passed=True),
        Check("Level 1 headings", passed=True),
        Check("Running head present", passed=False, detail="Missing"),
        Check("Title page correct", passed=False, detail="No author name found"),
        Check("Hanging indent on references", passed=False, detail="First-line indent detected"),
        Check("Margins", passed=False, detail="Left margin 0.75in, expected 1in"),
    ],
    errors=[],
    warnings=[
        "Font is Times New Roman 11pt, APA requires 12pt",
        "References not alphabetized",
    ],
)
```

**CLI additions:**

```bash
py -m docgraph paper.docx --detect-format       # → APA: 91%, MLA: 12%, ...
py -m docgraph paper.docx --validate apa         # → compliance score + issues
py -m docgraph paper.docx --report               # → HTML validation report
```

---

### Phase 3 — acewriter Integration

**Goal:** Replace acewriter's internal `analyzer.py` with docgraph.

**Strategy:**

1. Add dependency: `docgraph` (the new tools/docgraph/)
2. Replace `acewriter/lib/document/docx/analyzer.py` with a thin compatibility shim
3. Remove duplicated code from acewriter
4. Add `--format` and `--validate` flags to acewriter for score+humanize workflows

**Compatibility shim:**

```python
# New acewriter/lib/document/docx/analyzer.py — thin wrapper
from docgraph import open as docgraph_open

def detect_structure(docx_doc):
    """Compatibility shim — returns old DocumentStructure API."""
    doc = docgraph_open.from_docx(docx_doc)
    return doc.to_legacy_structure()
```

Or, better: gradually refactor acewriter's pipeline stages to use `DocumentGraph` directly, eliminating the shim.

**Files to remove from acewriter (already identified as duplicated/dead):**
- `lib/document/docx/analyzer.py` — replace with wrapper
- `lib/document/docx/writer.py` — `apply_highlights`, `replace_paragraphs_by_id` (dead)
- `lib/document/report.py` — `add_summary_page`, `render_summary`, `render_original_summary`, `_section_*`, `_score_*` (dead)
- `lib/document/report_assembler.py` — `assemble_report` (dead)
- `lib/rewrite.py` (whole module dead)
- `lib/budget.py` (whole module dead)
- `lib/detector/browser.py` (whole module dead)

---

### Phase 4 — Format Validators + Plugin System

| Phase | Feature | Effort |
|-------|---------|--------|
| 4a | IEEE format detector + validator | Medium |
| 4b | Chicago format detector + validator | Medium |
| 4c | Harvard format detector + validator | Medium |
| 4d | Plugin architecture (register format detectors/validators) | Medium |

### Phase 5 — More Parsers

| Phase | Feature | Effort |
|-------|---------|--------|
| 5a | Markdown parser | Low (text-based, structural hints from headings) |
| 5b | HTML parser | Low (similar to MD, plus `<section>`, `<article>`, etc.) |
| 5c | PDF parser | Very high (requires layout extraction, coordinates) |
| 5d | ODT parser | Medium |
| 5e | RTF parser | High |

### Phase 6 — Multi-Platform Distribution

| Phase | Feature | Effort |
|-------|---------|--------|
| 6a | CLI as standalone binary (PyInstaller) | Low |
| 6b | FastAPI JSON API server | Medium |
| 6c | npm wrapper (shells out to CLI or HTTP) | Low |
| 6d | VS Code extension (uses CLI) | Medium |
| 6e | Browser/WASM (via Pyodide or Rust core) | Very high |

---

## Existing Logic Analysis — acewriter `analyzer.py`

### What exists today (~925 lines in `lib/document/docx/analyzer.py`)

The acewriter analyzer is a **V4 document intelligence engine** that already implements 80% of the Phase 1 docgraph pipeline:

| Component | acewriter location | Status | Extraction strategy |
|-----------|-------------------|--------|-------------------|
| Paragraph extraction | `_build_paragraph_info()` L363-381 | Mature | Extract as-is to `parser/docx.py` |
| Heading detection | `_detect_headings()` L415-472 | Mature | Extract to `detectors/headings.py` |
| Feature extraction | `_extract_features()` L477-496 | Mature | Split into `features/*.py` |
| Score functions | `_score_body_v4()` etc. L503-601 | Mature | Move to `classifier/paragraph.py` |
| Classification | `_classify_paragraphs()` L665-676 | Mature | Move to `classifier/paragraph.py` |
| State machine | `_state_machine()` L704-729 | Works but no APPENDIX state | Extend (add APPENDIX region) |
| Region assembly | `_assemble_regions()` L744-765 | Mature | Move to `state_machine/document.py` |
| Main entry | `detect_structure()` L821-864 | Mature | Refactor as `parser/docx.parse()` |
| Debug output | `format_debug_output()` L872-924 | Useful | Port to CLI `--debug` |
| Constants | `SECTION_NAMES`, `REFERENCE_MARKERS`, etc. | Mature | Move to appropriate `detectors/` |
| Rewrite policies | `POLICIES` dict L772-785 | Acewriter-specific | Keep in acewriter |
| Duplicate class | `ParagraphScores` L110 and L203 | Bug (duplicate) | Fix: keep one |
| Dead class | `ParagraphScore` L175 | Dead | Remove (not in docgraph) |

### What's tightly coupled to acewriter that needs rework

1. **`RewritePolicy` enum + `POLICIES` dict** — Acewriter-specific (what to rewrite/copy/ignore). Move to acewriter's config, not docgraph.
2. **`detect_format()` / `convert_to_docx()`** in `base.py` — Document format detection + PDF→DOCX conversion. Keep in acewriter for now; docgraph will eventually have its own.
3. **`Document` dataclass** in `base.py` — Internal representation. Docgraph will have its own `DocumentGraph`.

---

## Potential Conflicts & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Duplicating code during extraction** | Two copies of the same logic diverge | Phase 3 integration must follow immediately after Phase 1. Keep extraction + integration in the same build cycle. |
| **Breaking acewriter during refactor** | Users can't process documents | Don't touch acewriter in Phase 1. Phase 3 is a separate PR with thorough testing. |
| **Over-generalizing models** | Models don't fit any format perfectly | Start with what acewriter needs. Extend when adding new parsers. |
| **State machine too simple** | Fails on complex documents (appendices, multi-body) | Add APPENDIX state. Use confidence-based transitions, not hard rules. |
| **Name collision: two `ReportModel` classes** | Confusion between `report_model.py` and `models/report.py` | Docgraph uses `DocumentGraph`. No collision. |
| **python-docx version compatibility** | Upstream API changes | Pin version in requirements.txt. |

---

## Backward Compatibility

- **Phase 1:** Zero impact on acewriter. New tool only.
- **Phase 3:** acewriter's `detect_structure()` return type must not change. Use compatibility shim.
- **CLI:** `py -m docgraph` is new — no existing users to break.

---

## Testing Strategy

| Layer | Test approach |
|-------|---------------|
| Models | Unit tests for dataclass construction + confidence computation |
| Parser (DOCX) | Integration tests with real .docx files (cover, body, references) |
| Classifier | Known-output tests: given features X, expect scores Y |
| State machine | Known-input tests: given paragraph sequence X, expect regions Y |
| Format detection | Test against known APA/MLA sample documents |
| CLI | `pytest` with `CliRunner` (click) or subprocess tests |
| Regression | Compare acewriter `detect_structure()` output with docgraph output on same .docx files |

### Sample files needed
- APA paper with cover, abstract, body, references
- MLA paper with Works Cited
- Simple business document (no academic format)
- Paper with appendix
- Paper with TOC

---

## Rollout Strategy

```
Step 1: Scaffold tools/docgraph/ with models only
    → Verify imports work
    → Verify model serialization
    → Design JSON schema first (language-neutral contract)

Step 2: Extract parser + features + classifier from acewriter
    → Test: output matches acewriter on 5+ .docx samples

Step 3: Build state machine + region assembly
    → Test: regions match acewriter
  
Step 4: Build JSON exporter + CLI
    → Test: py -m docgraph sample.docx --json
    → Verify: JSON output matches schema exactly

Step 5: Format detection + validation (Phase 2)
    → Test: APA paper returns APA > 80%

Step 6: acewriter integration (Phase 3)
    → Test: acewriter produces same output with docgraph backend

Step 7+: Multi-platform distribution (Phase 6)
    → CLI binary, npm wrapper, VS Code extension
```

---

## What we DO NOT build in Phase 1

| Feature | Why not |
|---------|---------|
| PDF parser | Extremely hard. Requires layout engine, coordinates, OCR. Future phase (5c). |
| Markdown/HTML parsers | Simple, but not needed for acewriter Phase 1. Future phase (5a, 5b). |
| Plugin system | Premature until we have 3+ format detectors. Future phase (4d). |
| Full format validators (APA, MLA, etc.) | Phase 2 detects **structure**, not format. Validators come in Phase 2. |
| npm wrapper | Python library first. npm wrapper (Phase 6c) shells out to CLI using the JSON contract. |
| VS Code extension | Phase 6d, after JSON API is stable. |
| REST API server | Phase 6b, after core is mature. |
| Highlighter/renderer UI | Acewriter already has this. Not docgraph's job. |
| Non-DOCX input | Phase 5+. |

---

## Success Criteria for Phase 1

```bash
# 0. Design JSON schema first (before writing any code)
#    — Schema lives at tools/docgraph/schema/v1.json
#    — Validated by tests/test_schema.py
#    — Same schema used by Python, CLI, and future npm/REST

# 1. Parse a real .docx
py -m docgraph sample.docx --json > ast.json

# 2. Output matches JSON schema exactly
python3 -c "
import json, jsonschema
d = json.load(open('ast.json'))
schema = json.load(open('tools/docgraph/schema/v1.json'))
jsonschema.validate(d, schema)
"

# 3. Output contains all expected fields
python3 -c "
d = json.load(open('ast.json'))
assert 'metadata' in d
assert 'paragraphs' in d
assert 'regions' in d
assert 'headings' in d
assert len(d['paragraphs']) > 0
assert d['regions'][0]['type'] == 'front_matter'
"

# 4. Structure matches acewriter output (same .docx → same regions)
python3 -c "
from acewriter.lib.document.docx.analyzer import detect_structure
# ... compare regions with docgraph output
"

# 5. CLI works for all flags
py -m docgraph --help
py -m docgraph sample.docx              # summary on stderr
py -m docgraph sample.docx --json       # JSON on stdout
py -m docgraph sample.docx --debug      # extended output
py -m docgraph sample.docx -o out.json  # save to file
```
