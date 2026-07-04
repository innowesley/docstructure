# DocStructure

Document structure analysis engine — parse `.docx` files, classify paragraphs, detect academic formats, and validate formatting rules.

```python
from docstructure import analyze, detect_format, validate

doc = analyze("paper.docx")
fmt = detect_format(doc)
report = validate(doc)
```

---

## Quick Start

```bash
# Install
pip install docstructure

# Analyze a document
docstructure analyze paper.docx

# Detect academic format
docstructure detect paper.docx
# → APA: 94% (title_page, abstract, doi, author_date_citations)

# Validate against a format
docstructure validate paper.docx
# → APA compliance: 83% (5/6 checks passed)
```

---

## Installation

### From PyPI (once published)

```bash
pip install docstructure
```

### From source (development)

```bash
git clone https://github.com/anomalyco/tools.git
cd tools/docstructure
pip install -e .
```

### Requirements

- Python 3.10+
- `python-docx` (automatically installed)

---

## CLI

```
docstructure {analyze,graph,detect,validate} [options] <source>
```

| Command | Description |
|---------|-------------|
| `analyze` | Full analysis pipeline → JSON |
| `graph` | Document graph → JSON |
| `detect` | Detect academic format (APA/MLA/IEEE) |
| `validate` | Validate against format rules |

### Global flags

| Flag | Description |
|------|-------------|
| `--verbose`, `-v` | Verbose output |
| `--version` | Show version |

### `analyze`

```bash
docstructure analyze paper.docx                         # JSON to stdout
docstructure analyze paper.docx -o output.json          # Save to file
docstructure analyze paper.docx --validate              # Analyze + validate
docstructure analyze paper.docx --schema v1             # Output v1 schema
```

### `detect`

```bash
docstructure detect paper.docx                          # Human-readable
docstructure detect paper.docx --json                   # JSON output
```

### `validate`

```bash
docstructure validate paper.docx                        # Auto-detect format
docstructure validate paper.docx --format apa           # Force APA rules
docstructure validate paper.docx --format mla -o out.json
```

---

## Python API

```python
from docstructure import analyze, parse, detect_format, validate, to_json, to_file
```

### `analyze(source: str) -> Document`

Full analysis pipeline: parse → normalize → extract features → classify → build regions → resolve relationships.

```python
doc = analyze("paper.docx")
```

### `parse(source: str) -> Document`

Parse only — no analysis. Useful when you want to inspect the raw document structure.

```python
doc = parse("paper.docx")
print(f"{len(doc.paragraphs)} paragraphs")
```

### `detect_format(doc: Document, threshold: float = 0.3) -> FormatDetection | None`

Detect academic format. Returns the highest-confidence detection above the threshold.

```python
result = detect_format(doc)
if result:
    print(f"{result.format_name}: {result.confidence:.0%}")
    # → APA: 94%
```

### `validate(doc: Document, rules: list[Rule] | None = None) -> list[RuleResult]`

Run validation rules against a document. With no arguments, runs default structural rules. Use format-specific rules for compliance checking.

```python
results = validate(doc)
for r in results:
    print(f"[{'PASS' if r.passed else 'FAIL'}] {r.message}")
```

### `serialize(doc: Document, schema_version: str = "v2") -> dict`

Serialize document to a dict matching the JSON schema.

```python
data = serialize(doc)
data["schema"]  # → schema URL
```

### `to_json(doc: Document, schema_version: str = "v2") -> str`

Serialize document to a JSON string.

### `to_file(doc: Document, path: str, schema_version: str = "v2") -> None`

Write document JSON to a file.

---

### Public API Stability

The following functions are guaranteed stable within the v0.x line:

- `analyze()`
- `parse()`
- `detect_format()`
- `validate()`
- `serialize()`
- `to_json()`
- `to_file()`

Everything else is internal and may change between minor versions.

---

## Architecture

DocStructure processes documents through a pipeline of six stages:

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  Parse   │→ │Normalize │→ │ Features │→ │Classify  │→ │ Regions  │→ │ Resolve  │
│          │  │          │  │          │  │          │  │          │  │          │
│ Physical │  │Clean     │  │Word/sent │  │Semantic  │  │State     │  │Edges     │
│ blocks   │  │text/runs │  │counts    │  │roles     │  │machine   │  │(heading, │
│          │  │          │  │          │  │          │  │          │  │citation) │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

**Key design principle:** Physical ≠ Semantic. The parser produces only physical blocks. Semantic classification happens later in the pipeline.

### Node types

| Type | Description |
|------|-------------|
| `ParagraphBlock` | Text paragraph with runs, role, heading level |
| `TableBlock` | Table with rows and cells |
| `ListBlock` | Ordered/bullet/checklist |
| `FigureBlock` | Image with caption |
| `CodeBlock` | Code snippet |
| `EquationBlock` | Math equation |
| `RegionNode` | Semantic region (title page, abstract, references...) |

### Paragraph roles

`BODY`, `HEADING`, `TITLE`, `METADATA`, `ABSTRACT`, `REFERENCE`, `CAPTION`, `TOC_ENTRY`, `APPENDIX`, `AUTHOR`, `FOOTNOTE`, `ENDNOTE`

### Region types

`TITLE_PAGE`, `ABSTRACT`, `TABLE_OF_CONTENTS`, `INTRODUCTION`, `METHODOLOGY`, `RESULTS`, `DISCUSSION`, `CONCLUSION`, `REFERENCES`, `APPENDIX`, `FRONT_MATTER`, `MAIN_CONTENT`, `BACK_MATTER`

---

## Schema

DocStructure uses JSON Schema for its output format. Two versions are maintained:

| Version | Status | Description |
|---------|--------|-------------|
| v1 | Deprecated | Original schema (bug fixes only) |
| v2 | Current | Adds `format_detection` and `validation` blocks |

Schema files: `output/schema/v1.json`, `output/schema/v2.json`

```bash
# Analyze with specific schema version
docstructure analyze paper.docx --schema v2    # default
docstructure analyze paper.docx --schema v1    # deprecated
```

---

## Validation

Validation is rule-based. Rules can be generic or format-specific.

### Default rules (always run)

| Rule | Description |
|------|-------------|
| `no_body_text` | Warns if document has no body paragraphs |
| `missing_sections` | Warns if document has few sections |
| `heading_order` | Warns if heading levels are skipped |

### Format-specific rules

| Format | Rules | Coverage |
|--------|-------|----------|
| APA 7th | 7 rules | Running head, abstract, references, DOI, heading order, font, author-date |
| MLA 9th | 5 rules | No title page, header, Works Cited, author-page citations, hanging indent |
| IEEE | 4 rules | Numbered references, section order, citation format, figure captions |

---

## Format Detection

DocStructure includes three academic format detectors:

| Detector | Signals | Weighted |
|----------|---------|----------|
| **APA 7th** | Title page, abstract, references section, DOI, author-date citations, running head, heading levels, serif font | 8 signals |
| **MLA 9th** | No title page, MLA header, Works Cited, author-page citations, student name, hanging indent | 6 signals |
| **IEEE** | Numbered references, Roman sections, inline citations, IMRAD sequence, Fig captions, serif font | 6 signals |

Each signal is scored independently. Final confidence is a weighted combination. Detectors auto-register via subclass discovery.

---

## Development

```bash
# Install in editable mode
pip install -e ./docstructure

# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Run benchmarks
python benchmarks/run.py
```

### Project structure

```
docstructure/
├── __init__.py          # Public API
├── __main__.py          # CLI
├── pyproject.toml       # Packaging
├── classifier/          # Semantic classification
├── core/                # Data types (Document, nodes, enums)
├── features/            # Feature extraction
├── formats/             # Format detection (APA, MLA, IEEE)
├── graph/               # Relationship resolution
├── normalizer/          # Text normalization
├── output/              # JSON serialization + schema
├── parser/              # Document parsers
├── validate/            # Validation rules
├── benchmarks/          # Performance benchmarks
├── tests/               # Test suites
```

---

## Changelog

See `docs/changelogs/` in the repository root.

---

## License

MIT
