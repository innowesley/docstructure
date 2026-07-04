# DocStructure — Document Structure Engine

**Status:** Draft  
**Target:** `tools/docstructure/` — new standalone tool  
**Relationship to acewriter:** Separate tool; acewriter will depend on it (Phase 3)

---

## Vision

Build a **semantic document structure engine** — not an APA parser, not a DOCX parser.

Think of it like **Tree-sitter for documents**: parse any format into a typed AST with confidence scores, then let plugins (APA validator, MLA checker, humanizer, citation extractor, RAG chunker, etc.) do their work on the AST.

```
.docx  .pdf  .odt  .html  .md
          │
          ▼
   Parser (per-format adapter)
          │
          ▼
   Feature Extraction
          │
          ▼
   Paragraph Classification
          │
          ▼
   Region Builder (state machine)
          │
          ▼
   Document Type Detection
          │
          ▼
   Style Detection (APA? MLA? IEEE?)
          │
          ▼
   Validation Rules
          │
          ▼
   JSON (language-neutral contract)
```

---

## Ecosystem Gap — Why This Doesn't Exist Yet

No mature open-source library (Python or npm) can reliably detect document structure, infer format, and validate compliance:

| Library | Good for | Missing |
|---------|----------|---------|
| `python-docx` | Reading DOCX styles, paragraphs, tables | No document understanding |
| `PyMuPDF` / `pdfplumber` | PDF text + layout | No academic structure |
| `GROBID` | Scientific papers (PDF) | Published articles only, not DOCX or student papers |
| `dedoc` | Some document structure | Not format-aware (APA/MLA) |
| `docx2python` / `mammoth` | Text/HTML extraction | No semantic analysis |
| `citeproc-py` / `bibtexparser` | Citation formatting | Don't analyze documents |
| `LanguageTool` / `Vale` | Writing style checks | Don't detect regions or formats |

**The gap** — and the opportunity — is combining wordprocessing formats + typography + layout analysis + classification + rule engines + style guides into one coherent system.

---

## Users — Much Bigger Than Students

| Who | What they need from the AST |
|-----|----------------------------|
| **AI humanizers** | Body text only (skip cover, references, headings) |
| **Citation tools** | Reference paragraphs + citation patterns |
| **APA/MLA checkers** | Headings, regions, format-specific rules |
| **PDF converters** | Document structure → section hierarchy |
| **Search engines** | Sections + headings for indexing |
| **LLM preprocessing** | Chunk boundaries at semantic region edges |
| **RAG systems** | Semantic regions (front matter ≠ body ≠ references) |
| **Academic software** | Bibliography structure |
| **Editors / word processors** | Navigation tree from heading hierarchy |
| **Accessibility tools** | Heading levels, reading order, alt-text regions |
| **Legal / contract analysis** | Clause boundaries, signature blocks, date fields |

The architecture must serve ALL of these — not just APA checkers.

---

## Platform Strategy

### What ships, and when

```
Phase 1    Python package (pip install docstructure)
Phase 2    CLI (docstructure analyze, validate, json)
Phase 3    acewriter integration
Phase 4    More parsers (PDF, MD, HTML, ODT)
Phase 5    npm package (thin wrapper around Python CLI)
Phase 6    REST API, VS Code extension
```

### Python + npm — both

```
Python (pip)    ← core engine (parsing, classification, format detection)
                       
npm (packaged)  ← thin wrapper calling Python CLI
                        or future native TypeScript port
```

The JSON output is the shared contract between them.

---

## Design Principles

### 1. Never hardcode surface patterns

| ❌ Bad | ✅ Good |
|--------|---------|
| `if text == "Student Name"` | Classify as `metadata` paragraph |
| `if text == "References"` | Detect `reference_heading` by features |
| `doc.is_apa` | `doc.format` returns `[FormatScore(APA, 94%)]` |

Language plugins map labels to generic types:

```
References     → reference_heading
Bibliography   → reference_heading
Works Cited    → reference_heading
Literatur      → reference_heading
Références     → reference_heading
```

The engine never knows which language — it just knows it found a reference heading.

### 2. Paragraph IDs are UUIDs

Don't rely on positional indexes:

```python
Paragraph(id="a1b2c3d4-...", index=17, ...)
Region(start="a1b2c3d4-...", end="e5f6g7h8-...")
```

Indexes exist for debugging. UUIDs are the canonical reference.

### 3. Confidence everywhere

Never return `"APA"`. Return `{"style": "APA", "confidence": 0.93}`.

Same for:
- Every paragraph classification
- Every region boundary
- Every format detection
- Every validation check

### 4. Parse ≠ Classify ≠ Detect ≠ Validate

Four separate pipeline stages:

```
parse()      → raw document model
classify()   → paragraph roles + regions
detect()     → format identification (APA/MLA/IEEE)
validate()   → compliance scoring
```

Each stage is independent. APA never decides structure. Structure already exists.

### 5. Edge cases from day one (25 production-grade rules)

The DOCX parser must handle these from the start — they're not future optimizations:

| # | Edge case | How |
|---|-----------|-----|
| 1 | **Blank ≠ empty** | `is_visual_blank` checks tabs, spaces, non-breaking spaces, hidden text, manual line breaks |
| 2 | **Page breaks** | Store `page_break_before`, `page_break_after` per paragraph |
| 3 | **Section breaks** | Store `section_break_type: str \| None` (Next Page, Continuous, Even Page, Odd Page) |
| 4 | **Paragraph spacing** | Store `space_before`, `space_after` in points — not inferred from blank paragraphs |
| 5 | **Style inheritance** | Check `style.base_style` hierarchy — not just `style.name` |
| 6 | **Outline levels** | Store `outline_level: int \| None` (Word stores this independently of style) |
| 7 | **Lists** | Store `list_level`, `list_id`, `numbering` — never detect bullets by text characters |
| 8 | **Tables** | Separate block nodes. Table cells are NOT paragraphs — classifier ignores them |
| 9 | **Captions** | Join multi-paragraph captions ("Figure 3." + "Revenue Growth") into one logical caption |
| 10 | **Headers/footers** | Detect and segregate into `doc.headers` / `doc.footers`. Exclude from body classification |
| 11 | **Text boxes** | Floating text boxes are not body. Segregate into `doc.text_boxes` |
| 12 | **Shapes** | SmartArt, callouts, diagrams → `doc.shapes`. Not body text |
| 13 | **Footnotes** | Separate region (`back_matter` subtype `footnotes`) |
| 14 | **Endnotes** | Separate region (`back_matter` subtype `endnotes`) |
| 15 | **Comments** | Ignore during analysis (available separately if requested) |
| 16 | **Track Changes** | Option to accept/reject: `parser_options = {"accept_track_changes": False}` |
| 17 | **Hidden text** | Ignore by default. APA templates hide instructions in hidden paragraphs |
| 18 | **Fields** | PAGE, DATE, TOC fields → store as `Field` type. Don't treat as metadata content |
| 19 | **TOC region** | Table of contents is a distinct region, not body text |
| 20 | **Multiple reference sections** | Support nested regions. Document can have "Chapter 1 References" + "Chapter 2 References" |
| 21 | **Appendices** | Appendix region. Paragraphs inside appendix look like body but ARE NOT body |
| 22 | **Expanded region types** | Beyond FRONT/BODY/BACK: COVER, TITLE_PAGE, METADATA, ABSTRACT, TOC, BODY, TABLES, FIGURES, REFERENCES, APPENDIX, FOOTNOTES, ENDNOTES |
| 23 | **OCR PDF abstraction** | Parser adapter interface keeps PDF logic completely separate from classification |
| 24 | **Confidence** | Every classification, region boundary, format detection, and validation check has a confidence score |
| 25 | **Parser never knows format** | The parser only produces paragraphs + features + layout. Format detection is a separate pipeline stage |

These are not "nice to haves." Every single one will cause incorrect output if missed. The acewriter analyzer currently fails on most of these — docstructure must not.  

### 6. The compiler analogy

Think of the pipeline as a compiler:

```
DOCX/PDF/HTML    (source code)
     │
     ▼
Lexer (parser)   (tokens → paragraphs)
     │
     ▼
AST (Document)   (paragraphs + features + layout)
     │
     ▼
Semantic Analysis (classification + regions)
     │
     ▼
Code Generation  (JSON, validation reports, etc.)
```

The parser is the **lexer**. The document model is the **AST**. Region detection is **semantic analysis**. Format validators are **linters**. This separation keeps each stage testable and replaceable.

---

## Data Model — Paragraph (25 Edge Cases Mapped)

Every edge case from the table above maps to a model field or a parser behavior:

```python
@dataclass
class Paragraph:
    id: str                          # UUID (#2)
    index: int                       # Positional index (for debugging only, #2)
    text: str                        # Visible text (stripped of hidden content, #17)

    # Visual blank detection (#1)
    is_visual_blank: bool            # True if only whitespace/hidden/breaks
    raw_xml: str | None              # Kept for debugging blank detection

    # Page and section breaks (#2, #3)
    page_break_before: bool
    page_break_after: bool
    section_break_type: str | None   # "next_page" | "continuous" | "even_page" | "odd_page" | None

    # Spacing (#4)
    space_before: float | None       # Points
    space_after: float | None        # Points

    # Style hierarchy (#5)
    style_name: str                  # Direct style name
    style_base: str | None           # Inherited style (e.g., "Normal" → "Quote")
    style_hierarchy: list[str]       # Full chain: ["Quote", "Normal", "Default"]

    # Outline and lists (#6, #7)
    outline_level: int | None        # Word's outline level (independent of style)
    is_list_item: bool               # Detected via numbering, NOT bullet chars
    list_level: int | None           # 0 = top level
    list_id: str | None              # Groups items in same list
    numbering_format: str | None     # "decimal", "bullet", "legal", "lowerLetter", etc.

    # Table awareness (#8)
    in_table: bool
    table_id: str | None             # UUID of parent table

    # Caption joining (#9)
    is_caption_start: bool           # First paragraph of a multi-par caption
    is_caption_continuation: bool    # Continuation paragraphs joined to caption

    # Hidden / filtered content (#15, #16, #17)
    is_hidden: bool                  # Hidden text (font property)
    has_track_changes: bool          # Whether tracked changes exist
    accept_track_changes: bool       # Parser option — apply or ignore

    # Field detection (#18)
    is_field: bool
    field_type: str | None           # "PAGE", "DATE", "TOC", "AUTHOR", etc.

    # Classification (output of classifier, not parser)
    role: ParagraphRole              # "body" | "heading" | "title" | "metadata" | ...
    confidence: float                # Classification confidence (#24)
    scores: ParagraphScores          # Raw scores per role

    # Features (extracted by features/* modules)
    features: ParagraphFeatures
```

## Data Model — Region Types (Expanded)

Beyond acewriter's 3-region model (FRONT→BODY→BACK), docstructure uses 13 region types:

| Region type | Enum | Detected by |
|-------------|------|-------------|
| Cover page | `COVER` | Centered text, name + affiliation pattern |
| Title page | `TITLE_PAGE` | Title centered, author, institutional affiliation |
| Metadata block | `METADATA` | Keywords, author note, correspondence info |
| Abstract | `ABSTRACT` | "Abstract" heading + single-paragraph block |
| Table of Contents | `TOC` | "Table of Contents" heading + leader-dot lines |
| Body | `BODY` | Continuous body paragraphs, headings, lists |
| Tables section | `TABLES` | "Tables" section (APA table-heavy papers) |
| Figures section | `FIGURES` | "Figures" section (APA figure-heavy papers) |
| References | `REFERENCES` | "References" heading + hanging-indent paragraphs |
| Appendix | `APPENDIX` | "Appendix A" heading + its content, can nest |
| Footnotes | `FOOTNOTES` | Separate section at page bottom / document end |
| Endnotes | `ENDNOTES` | Separate section at document end |
| Back matter | `BACK_MATTER` | Catch-all for other end material |

```python
@dataclass
class Region:
    type: RegionType                 # One of the 13 above
    subtype: str | None              # e.g., "chapter1_references" for nested refs
    label: str | None                # "Appendix A", "Chapter 1 References"
    paragraph_ids: list[str]         # UUIDs in order
    start_index: int                 # Debugging convenience
    end_index: int                   # Debugging convenience
    confidence: float                # Boundary confidence (#24)
    signals: list[Signal]            # Evidence for this region boundary
```

---

## Directory Structure

```
tools/docstructure/
├── __init__.py
├── __main__.py                    # CLI entry
├── core/                          # Language-independent models
│   ├── __init__.py
│   ├── document.py                # DocumentGraph
│   ├── paragraph.py               # Paragraph, ParagraphRole, BlockType
│   ├── section.py                 # Region, RegionType
│   ├── table.py                   # Table, TableRow, TableCell
│   ├── run.py                     # Run (inline formatting)
│   └── base.py                    # Signal, Heading, Span
├── parser/                        # Format adapters
│   ├── __init__.py                # Parser base class + registry
│   ├── base.py                    # Abstract parser interface
│   ├── docx.py                    # DOCX adapter (extracted from acewriter)
│   └── ...                        # md.py, pdf.py, odt.py (future)
├── features/                      # Feature extraction
│   ├── __init__.py
│   ├── lexical.py                 # Word count, sentence count, vocabulary
│   ├── typography.py              # Font, size, bold, italic, mono, case
│   ├── spacing.py                 # Indentation, blank lines, alignment
│   └── numbering.py               # Outline level, bullet detection
├── classifier/                    # Paragraph + document classification
│   ├── __init__.py
│   ├── paragraph.py               # Score functions → BlockType
│   ├── sections.py                # Section/region classification
│   ├── citation.py                # Citation pattern detection
│   └── styles.py                  # Style name → BlockType mapping
├── formats/                       # Format detectors (plugins)
│   ├── __init__.py                # Registry + base class
│   ├── base.py                    # FormatDetector + FormatValidator ABCs
│   ├── apa.py                     # APA 7th edition detector + validator
│   ├── mla.py                     # MLA 9th edition detector + validator
│   ├── ieee.py                    # IEEE detector + validator (future)
│   ├── chicago.py                 # Chicago detector + validator (future)
│   └── acm.py                     # ACM detector + validator (future)
├── output/                        # Exporters
│   ├── __init__.py
│   ├── json.py                    # Language-neutral JSON export
│   ├── html.py                    # HTML report (future)
│   └── report.py                  # Terminal report
└── schema/
    └── v1.json                    # JSON schema (the API contract)
```

---

## Revised JSON Schema (Language-Neutral Contract)

```json
{
  "document_type": "academic_paper",

  "format": {
    "style": "APA",
    "confidence": 0.94,
    "version": 7,
    "alternatives": [
      {"style": "MLA", "confidence": 0.12},
      {"style": "IEEE", "confidence": 0.06}
    ]
  },

  "metadata": {
    "source": "paper.docx",
    "parser": "docx",
    "paragraph_count": 142,
    "page_count": null
  },

  "regions": [
    {
      "type": "COVER",
      "label": null,
      "paragraph_ids": ["uuid-1", "uuid-2", "uuid-3"],
      "start_index": 0,
      "end_index": 3,
      "confidence": 95,
      "signals": [
        {"name": "centered_text", "score": 8},
        {"name": "author_affiliation", "score": 5}
      ]
    },
    {
      "type": "ABSTRACT",
      "label": null,
      "paragraph_ids": ["uuid-4"],
      "start_index": 4,
      "end_index": 4,
      "confidence": 90
    },
    {
      "type": "TOC",
      "label": null,
      "paragraph_ids": ["uuid-5", "uuid-6", "uuid-7"],
      "start_index": 5,
      "end_index": 10,
      "confidence": 88
    },
    {
      "type": "BODY",
      "paragraph_ids": ["uuid-8", "uuid-9", ...],
      "start_index": 11,
      "end_index": 128,
      "confidence": 98
    },
    {
      "type": "REFERENCES",
      "label": null,
      "paragraph_ids": ["uuid-129", ...],
      "start_index": 129,
      "end_index": 141,
      "confidence": 96
    },
    {
      "type": "APPENDIX",
      "label": "Appendix A",
      "paragraph_ids": ["uuid-142", ...],
      "start_index": 142,
      "end_index": 155,
      "confidence": 92
    }
  ],

  "paragraphs": [
    {
      "id": "a1b2c3d4-e5f6-...",
      "index": 12,
      "text": "Artificial intelligence has transformed...",
      "class": "body",
      "role": "body",
      "confidence": 0.99,

      "is_visual_blank": false,          # Edge case #1
      "page_break_before": false,         # Edge case #2
      "page_break_after": false,          # Edge case #2
      "section_break_type": null,         # Edge case #3
      "space_before": 0.0,                # Edge case #4
      "space_after": 6.0,                 # Edge case #4
      "outline_level": null,              # Edge case #6
      "is_list_item": false,              # Edge case #7
      "in_table": false,                  # Edge case #8
      "is_hidden": false,                 # Edge case #17

      "features": {
        "word_count": 24,
        "sentence_count": 2,
        "font_size": 12.0,
        "bold": false,
        "italic": false,
        "centered": false,
        "monospace": false,
        "alignment": "left",
        "style_name": "Normal",
        "style_base": "Normal",            # Edge case #5
        "styled_hierarchy": ["Normal"]     # Edge case #5
      },
      "scores": {
        "body": 12,
        "heading": 1,
        "title": 0,
        "metadata": 0,
        "reference": 0,
        "caption": 0,
        "toc": 0,
        "abstract": 0
      }
    }
  ],

  "headings": [
    {
      "id": "uuid-...",
      "paragraph_id": "uuid-42",
      "level": 1,
      "text": "Introduction",
      "confidence": 97
    }
  ],

  "tables": []
}
```

---

## Phase Plan

### Phase 1 — Core Engine + DOCX (this build)

**Goal:** DOCX → Document AST → JSON. CLI working. Regression-match acewriter output.

| Layer | Source | Edge cases addressed |
|-------|--------|---------------------|
| `core/` models | Refactored from acewriter `analyzer.py` (ParagraphInfo → Paragraph, etc.) | #1-#25 — full model fields (see data model below) |
| `parser/docx.py` | Extracted from acewriter `_build_paragraph_info()` + `_detect_headings()` | #1-#18 — blank detection, breaks, styles, outlines, lists, tables, headers/footers, text boxes, shapes, footnotes, endnotes, comments, track changes, hidden text, fields |
| `features/*` | Extracted from acewriter `_extract_features()`, split by domain | #5-#7 — style inheritance, outline levels as features |
| `classifier/paragraph.py` | Extracted from acewriter `_compute_scores()` + `_classify_paragraphs()` | #19-#22 — TOC, multiple references, appendices, expanded region types |
| `classifier/sections.py` | State machine (FRONT→BODY→BACK) from acewriter `_state_machine()` | #19-#22 — 13 region types with confidence-based transitions |
| `output/json.py` | New — language-neutral JSON export | #24 — confidence everywhere |
| `__main__.py` | CLI with subcommands | — |

**API:**

```python
import docstructure

doc = docstructure.open("paper.docx")

# Core access
doc.type                # → "academic_paper" | "report" | "letter" | ...
doc.paragraphs          # → list[Paragraph] (each with UUID id)
doc.regions             # → list[Region]
doc.headings            # → list[Heading]
doc.tables              # → list[Table]

# Format (Phase 2 fills this)
doc.format              # → None in Phase 1 (no format detection yet)

# Validation (Phase 2+)
doc.validate("APA")     # → NotImplementedError in Phase 1

# Export
doc.to_json()           # → dict (matches v1 schema)
```

**CLI:**

```bash
docstructure analyze paper.docx          # → structure summary (stderr)
docstructure analyze paper.docx --json   # → JSON AST (stdout)

docstructure json paper.docx             # → JSON only (for piped usage)
docstructure json paper.docx -o out.json # → save to file
```

**Dependencies (add to `tools/requirements.txt`):**
- `python-docx` (already present)
- `rich` (already present)
- `jsonschema` (for schema validation in tests)

No new runtime dependencies beyond what acewriter already uses.

**Files to create:**

```
tools/docstructure/__init__.py
tools/docstructure/__main__.py
tools/docstructure/core/__init__.py
tools/docstructure/core/document.py
tools/docstructure/core/paragraph.py
tools/docstructure/core/section.py
tools/docstructure/core/table.py
tools/docstructure/core/run.py
tools/docstructure/core/base.py
tools/docstructure/parser/__init__.py
tools/docstructure/parser/base.py
tools/docstructure/parser/docx.py
tools/docstructure/features/__init__.py
tools/docstructure/features/lexical.py
tools/docstructure/features/typography.py
tools/docstructure/features/spacing.py
tools/docstructure/features/numbering.py
tools/docstructure/classifier/__init__.py
tools/docstructure/classifier/paragraph.py
tools/docstructure/classifier/sections.py
tools/docstructure/output/__init__.py
tools/docstructure/output/json.py
tools/docstructure/schema/v1.json
```

---

### Phase 2 — Format Detection + Validation

**Goal:** Detect document type (academic paper, report, resume, ...) and format (APA/MLA/IEEE), then validate compliance.

**Architecture:**

```
DocumentGraph
    │
    ▼
FormatDetector.detect(graph)
    │  Each plugin just answers: "Does this look like my format?"
    │
    ├── APA: 94%    (cover + abstract + references + DOI + heading hierarchy)
    ├── MLA: 12%    (no cover, Works Cited, parenthetical author-page)
    ├── IEEE: 6%    (numbered references, specific heading style)
    └── Resume: 3%  (contact section, work history, bullet lists)
```

**Format plugin interface:**

```python
class FormatDetector(ABC):
    @abstractmethod
    def score(self, doc: DocumentGraph) -> FormatScore:
        """Score how well this document matches my format.
        Returns 0.0 (no match) to 1.0 (perfect match).
        """
```

**Validator output:**

```python
ValidationResult(
    format="APA",
    detection_confidence=0.94,
    compliance_score=0.67,
    checks=[
        Check("References page exists", passed=True),
        Check("APA citations detected", passed=True),
        Check("Running head present", passed=False, detail="Missing"),
        Check("Title page correct", passed=False, detail="No author affiliation"),
    ],
    errors=[...],
    warnings=["Font is 11pt, APA requires 12pt", ...],
)
```

**CLI:**

```bash
docstructure detect paper.docx            # → APA: 94%, MLA: 12%
docstructure validate paper.docx          # → compliance score + issues
docstructure validate paper.docx --format apa
```

---

### Phase 3 — acewriter Integration

**Goal:** Replace acewriter's internal `analyzer.py` with docstructure.

**Shim:**

```python
# New acewriter/lib/document/docx/analyzer.py
from docstructure import open as ds_open

def detect_structure(docx_doc):
    """Compatibility shim — returns old DocumentStructure API."""
    doc = ds_open.from_docx(docx_doc)
    return doc.to_legacy_structure()
```

**Dead code to remove from acewriter (from earlier scan):**
- `lib/budget.py` (whole module)
- `lib/rewrite.py` (whole module)
- `lib/detector/browser.py` (whole module)
- `lib/document/docx/analyzer.py` → replace with shim
- `lib/document/docx/writer.py` — `apply_highlights`, `replace_paragraphs_by_id`
- `lib/document/report.py` — `add_summary_page`, `render_summary`, `render_original_summary`, `_section_*`, `_score_*`
- `lib/document/report_assembler.py` — `assemble_report`, `_scores_dict_from_results`, `build_metadata`

---

### Phase 4 — More Parsers

| Parser | Effort | Approach |
|--------|--------|----------|
| Markdown | Low | Headings → structure, code blocks, lists |
| HTML | Low | `<section>`, `<article>`, `<h1>`–`<h6>`, semantic elements |
| ODT | Medium | XML-based, similar to DOCX but different schema |
| PDF | Very high | Layout extraction, coordinates, OCR. Adapter pattern. |

**Adapter interface:**

```python
class Parser(ABC):
    @abstractmethod
    def parse(self, source: str | Path) -> DocumentGraph:
        """Parse source file into a DocumentGraph."""
```

Each parser fills the same `DocumentGraph` model. The classifier and formatters never know which parser produced the data.

---

### Phase 5 — Multi-Platform Distribution

| Deliverable | How |
|-------------|-----|
| **pip package** | `pyproject.toml` → `pip install docstructure` |
| **CLI binary** | PyInstaller → standalone binary |
| **npm package** | Shells out to Python CLI; parses JSON result |
| **REST API** | FastAPI server wrapping the core |
| **VS Code extension** | Calls CLI or REST API |

The npm package in Phase 5b:

```javascript
// npm install docstructure (requires Python CLI installed)
import { analyze } from "docstructure";

const result = await analyze("paper.docx");
// result = JSON object (matches v1 schema exactly)
console.log(result.format.style);  // "APA"
```

---

## Format Detection Plugin Design

Each format is a plugin file under `formats/`:

```
formats/
├── __init__.py        # Auto-discovers all FormatDetector subclasses
├── base.py            # FormatDetector + FormatValidator ABCs
├── apa.py             # APA 7th edition
├── mla.py             # MLA 9th edition
├── ieee.py            # IEEE
├── chicago.py         # Chicago Manual of Style
└── acm.py             # ACM
```

**Plugin contract:**

```python
class APADetector(FormatDetector):
    name = "APA"
    version = 7

    def score(self, doc: DocumentGraph) -> FormatScore:
        signals = 0
        total = 0

        # Front matter: cover page with author/affiliation?
        total += 1
        if doc.has_cover_page():
            signals += 1

        # Abstract present?
        total += 1
        if doc.has_abstract():
            signals += 1

        # References section?
        total += 2
        ref_region = doc.get_region("references")
        if ref_region:
            signals += 2
            # Reference format checks
            if self._has_hanging_indents(ref_region):
                signals += 1
            total += 1
            if self._has_doi_patterns(ref_region):
                signals += 1
                total += 1

        # Heading hierarchy (Level 1, 2, 3)?
        total += 1
        if doc.heading_levels() == [1, 2, 3]:
            signals += 1

        # Running head?
        total += 1
        if self._has_running_head(doc):
            signals += 1

        confidence = signals / total if total > 0 else 0.0
        return FormatScore(name=self.name, version=self.version, confidence=confidence)
```

The engine runs ALL plugins and returns sorted results:

```python
doc.detect_format()
# → [
#     FormatScore("APA", version=7, confidence=0.94),
#     FormatScore("MLA", version=9, confidence=0.12),
#     FormatScore("IEEE", confidence=0.06),
#   ]
```

---

## Existing Logic Analysis — acewriter `analyzer.py`

### What extracts cleanly

| Component | acewriter location | Extraction target |
|-----------|-------------------|-------------------|
| Paragraph extraction | `_build_paragraph_info()` L363-381 | `parser/docx.py` |
| Heading detection | `_detect_headings()` L415-472 | `classifier/sections.py` |
| Feature extraction | `_extract_features()` L477-496 | `features/lexical.py`, `features/typography.py` |
| Score functions | `_score_body_v4()` etc. L503-601 | `classifier/paragraph.py` |
| Classification | `_classify_paragraphs()` L665-676 | `classifier/paragraph.py` |
| State machine | `_state_machine()` L704-729 | `classifier/sections.py` |
| Region assembly | `_assemble_regions()` L744-765 | `classifier/sections.py` |
| Main entry | `detect_structure()` L821-864 | `parser/docx.parse()` |
| Debug output | `format_debug_output()` L872-924 | `output/report.py` |
| Constants | `SECTION_NAMES`, `REFERENCE_MARKERS` | Move to `features/` or relevant classifier |
| Rewrite policies | `POLICIES` L772-785 | Acewriter-specific — keep in acewriter |

### What needs rework

1. **Integer paragraph indexes → UUIDs.** Add id generation.
2. **No APPENDIX state.** Extend state machine.
3. **Duplicate `ParagraphScores` class** (L110 and L203). Fix: keep one.
4. **Dead `ParagraphScore` class** (L175). Remove.
5. **Hardcoded `"References"`, `"Student Name"`.** Replace with generic classification.
6. **25 edge case gaps.** acewriter fails on most of these: no `is_visual_blank`, no page/section break tracking, no style inheritance chain, no outline levels, no list detection (uses bullet char check), no header/footer segregation, no text box/shape filtering, no footnotes/endnotes regions, no hidden text filtering, no field awareness, no TOC region, no multiple reference sections, no appendix region, no expanded region types. **docstructure must NOT inherit these gaps.**

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Duplicating code** during extraction | Phase 3 integration immediately after Phase 1 |
| **Breaking acewriter** | Don't touch acewriter in Phase 1. Separate PR with compat shim. |
| **Over-generalized models** | Start with acewriter's needs, extend for new parsers |
| **State machine too simple** | Add APPENDIX state; use confidence-based transitions |
| **Format plugin avalanche** | Ship core + APA only in Phase 2; add others as separate PRs |
| **python-docx API changes** | Pin version in requirements.txt |
| **npm wrapper complexity** | JSON contract keeps it simple — just shell + parse |
| **Edge case gaps** from acewriter carryover | All 25 edge cases explicitly listed in data model. Parser code must handle each from day one. Unit tests for each edge case. |
| **Blank paragraph misclassification** | `is_visual_blank` logic must check tabs, spaces, NBSP, hidden text, manual line breaks — not just `text.strip() == ""` |
| **List detection via bullet chars** | Always use numbering definition from DOCX XML. Never match on "•", "-", "*" characters. |
| **Header/footer leaking into body** | python-docx separates headers/footers at document level, not paragraph level. Parser must explicitly collect from `doc.sections[].header/footer` and exclude from body. |

---

## Backward Compatibility

- **Phase 1:** Zero impact. New tool only.
- **Phase 3:** acewriter `detect_structure()` return type must not change. Compatibility shim provided.
- **CLI:** New tool — no existing users to break.

---

## Testing Strategy

| Layer | Testing approach |
|-------|-----------------|
| **Models** | Unit tests: construction, serialization, confidence math |
| **DOCX parser** | Integration tests against real .docx samples |
| **Edge case tests** | One test per edge case (#1-#25): blank paragraphs, page breaks, section breaks, lists, tables, hidden text, TOC, etc. |
| **Classifier** | Known-feature → expected-score tests |
| **Regions** | Known-paragraph-sequence → expected-region tests |
| **Format detection** | Known APA/MLA .docx → expected format scores |
| **JSON output** | Validate against `schema/v1.json` with `jsonschema` |
| **CLI** | Subprocess tests for all subcommands |
| **Regression** | Same .docx processed by acewriter AND docstructure → same regions |

### Sample documents needed
- APA paper (cover, abstract, body, references)
- MLA paper (header, Works Cited)
- Business report (no academic format)
- Paper with appendix
- Paper with TOC, lists, tables, figures
- Paper with numbered headings (1.1, 1.2)
- Paper with footnotes and endnotes (edge cases #13, #14)
- Paper with hidden text / track changes (edge cases #15, #16, #17)
- Paper with multiple reference sections (edge case #20)
- Document with text boxes and shapes (edge cases #11, #12)
- Document with section breaks (edge case #3)
- Document with blank/near-blank paragraphs (edge case #1)

---

## Rollout Steps

```
Step 1: Design JSON schema first → schema/v1.json
        (This IS the API contract. Everything else implements it.)

Step 2: Core models → core/ (Paragraph, Region, DocumentGraph, etc.)
        UUID generation, serialization

Step 3: DOCX parser → parser/docx.py
        Paragraph extraction + heading detection
        Edge case handling: #1 (is_visual_blank), #2-#3 (page/section breaks),
          #4 (spacing), #5 (style inheritance), #6 (outline levels),
          #7 (lists via numbering), #8 (tables), #10-#12 (headers/footers,
          text boxes, shapes), #13-#14 (footnotes/endnotes),
          #15-#17 (comments, track changes, hidden text), #18 (fields)
        Test: output matches acewriter on 5+ .docx files
        Test: each edge case #1-#18 has at least one passing test

Step 4: Features → features/
        lexical, typography, spacing, numbering
        Test: feature extraction matches acewriter

Step 5: Classifier → classifier/
        Score functions + state machine
        Test: classification + regions match acewriter

Step 6: JSON output → output/json.py
        Test: output validates against schema/v1.json

Step 7: CLI → __main__.py
        Subcommands: analyze, json
        Test: all flags work

Step 8: Verify regression
        Same .docx → same regions as acewriter
```

---

## What we DO NOT build in Phase 1

| Feature | Why deferred |
|---------|--------------|
| PDF parser | Extremely hard (layout, coordinates, OCR). Phase 4. |
| Markdown/HTML parsers | Simple but not needed yet. Phase 4. |
| Format detection (APA/MLA) | Phase 2. Phase 1 detects **structure**, not format. |
| Format validation | Phase 2. Requires format detection first. |
| npm package | Phase 5. Python core must stabilize first. |
| REST API | Phase 6. Premature without users. |
| VS Code extension | Phase 6. After CLI is proven. |
| Plugin hot-loading | Phase 5. Start with ship-together plugins. |
| Resume / legal / book detectors | Format plugin system. Add when needed. |

**Edge cases ARE in scope for Phase 1.** All 25 edge cases must be handled by the parser, data model, and classifier from day one. The phase 1 definition of "done" includes passing edge case tests.

---

## Success Criteria for Phase 1

```bash
# 0. Schema exists
ls docstructure/schema/v1.json

# 1. Parse a real .docx
docstructure analyze sample.docx --json > ast.json

# 2. JSON validates against schema
python3 -c "
import json, jsonschema
schema = json.load(open('docstructure/schema/v1.json'))
data = json.load(open('ast.json'))
jsonschema.validate(data, schema)
"

# 3. Output has expected shape
python3 -c "
d = json.load(open('ast.json'))
assert 'document_type' in d
assert 'paragraphs' in d
assert 'regions' in d
assert 'headings' in d
assert len(d['paragraphs']) > 0
assert d['regions'][0]['type'] in ('COVER', 'TITLE_PAGE', 'ABSTRACT', 'BODY', 'REFERENCES')
assert d['paragraphs'][0]['id']  # UUID
"

# 4. Edge cases handled
# All 25 edge cases should have at least one passing test:
python3 -m pytest tests/ -k "edge" -v 2>/dev/null || echo "Edge case tests TBD"

# 5. Regions match acewriter
python3 -c "
from acewriter.lib.document.docx.analyzer import detect_structure
# ... compare regions
"

# 6. CLI works
docstructure analyze sample.docx       # summary on stderr
docstructure analyze sample.docx --json # JSON on stdout
docstructure json sample.docx           # JSON only
docstructure json sample.docx -o out.json
docstructure --help
```
