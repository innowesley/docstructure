# DocStructure v2 — Document Graph Engine

**Status:** Draft  
**Target:** `tools/docstructure/` — new standalone tool  
**Relationship to acewriter:** Separate tool; acewriter will depend on it (Phase 3)

---

## Vision

Build a **document graph engine** — not an APA checker, not a DOCX parser.

Think of it as a **compiler for documents**: parse any format into a normalized, typed, queryable graph with confidence scores, provenance, and plugin-based analysis pipelines. Consumers (validators, humanizers, citation extractors, RAG chunkers, accessibility tools) work on the same graph.

```
.docx  .pdf  .html  .md  .odt  .epub  .rtf
           │
           ▼
    Parser (per-format adapter)
      ↓
    Normalizer (Unicode, runs, whitespace, hidden text)
      ↓
    Feature Extractors (plugin registry, lazy)
      ↓
    Block Classifiers (role, type, confidence)
      ↓
    Region Builder (semantic regions from classified blocks)
      ↓
    Relationship Resolver (edges: citation→reference, heading→section)
      ↓
    Format Detectors (APA? MLA? Resume? Contract?)
      ↓
    Rule Engine / Validators (compliance, accessibility, custom)
      ↓
    Exporters (JSON, HTML, report, ...)
```

Each stage returns a **new immutable DocumentGraph**. No stage mutates the output of a previous stage.

---

## Core Philosophy

### 1. Physical ≠ Semantic

The parser produces **physical blocks** — paragraphs, runs, tables, images, section breaks.

The classifier produces **semantic meaning** — this paragraph is a heading, this region is the body.

The parser **never** produces `Reference`, `Title`, `Abstract`. It produces `Paragraph(style_name="Normal", text=...)`. The classifier decides what it means.

### 2. DocumentGraph, not AST

Documents are not trees. They are graphs with multiple sub-graphs:

- **Block graph** — ordered sequence of all content blocks (physical)
- **Inline graph** — runs within paragraphs (text, bold, citations, hyperlinks)
- **Semantic graph** — regions, headings, roles (meaning)
- **Relationship graph** — edges between blocks (citation→reference, heading→section)
- **Layout graph** — pages, columns, coordinates (PDF, optional)

### 3. Provenance everywhere

Every fact carries a shared `Provenance` dataclass rather than repeating the same fields:

```python
@dataclass
class Provenance:
    confidence: float          # 0.0 – 1.0
    produced_by: str           # "paragraph_classifier/v1.2"
    version: str               # Semantic version of the producing component
    evidence: list[str]        # Why? ["centered", "bold", "outline_level=1"]
```

Used by `Block`, `Region`, `Edge`, `Diagnostic` — never duplicated.

### 4. Stages are pure and independent

Each pipeline stage:

- Takes a `DocumentGraph`
- Returns a **new** `DocumentGraph`
- Never modifies the input
- Can be skipped, reordered, or run in isolation

### 5. Everything is a plugin

- Parsers (per MIME type)
- Feature extractors (registered, lazy)
- Classifiers (academic, legal, medical, resume)
- Format detectors (APA, MLA, IEEE)
- Validators (format-specific, accessibility, custom)
- Exporters (JSON, HTML, report)

### 6. Pipeline is discoverable

Each parser advertises capabilities:

```python
ParserCapabilities(
    supports_layout=False,
    supports_fonts=True,
    supports_tables=True,
    supports_images=True,
    supports_fields=True,
    supports_comments=False,
    supports_track_changes=True,
)
```

Validators check capabilities and degrade gracefully.

---

## Data Model

### Document

Document is organized into three domains — `graph` for the physical+semantic model, `analysis` for computed results, and `metadata` for versioning/provenance. This prevents the document from becoming a flat dumping ground as new features are added.

```python
@dataclass
class Document:
    id: DocumentId
    graph: DocumentGraph            # Physical + semantic model
    analysis: DocumentAnalysis      # Computed results
    metadata: DocumentMetadata      # Versions, source, language

@dataclass
class DocumentGraph:
    _node_index: dict[int, GraphNode]  # id → node (built once, cache)
    _edges_from: dict[int, list[Edge]] # source_id → edges (built once, cache)

    @property
    def nodes(self) -> list[GraphNode]:
        return list(self._node_index.values())

    @property
    def blocks(self) -> list[BlockNode]:
        return [n for n in self.nodes if isinstance(n, BlockNode)]

    @property
    def regions(self) -> list[RegionNode]:
        return [n for n in self.nodes if isinstance(n, RegionNode)]

    def get_node(self, id: int) -> GraphNode | None:
        return self._node_index.get(id)

    def edges_from(self, source_id: int) -> list[Edge]:
        return self._edges_from.get(source_id, [])

@dataclass
class DocumentAnalysis:
    diagnostics: list[Diagnostic]   # Validation results
    references: list[ReferenceNode] # Structured reference entries
    # Future: summaries, statistics, readability scores...

@dataclass
class DocumentMetadata:
    ast_version: str                # "docstructure/v1"
    parser_version: str             # "docx/1.0"
    parser_capabilities: ParserCapabilities
    source: str | None              # Filename or identifier
    language: str                   # ISO 639-1, "unknown" by default
    language_confidence: float

@dataclass
class DocumentId:
    document_id: str           # sha256(normalized_content) — stable identity
    instance_id: str           # UUID — this parse session
```

### GraphNode (base for all typed nodes)

```python
@dataclass
class GraphNode:
    id: int                    # Stable integer identity (per-document)
    provenance: Provenance     # Who created this, how confident, why
```

All typed nodes inherit from `GraphNode`. This lets `Edge` connect any node type.

### BlockNode (base for all content blocks)

```python
@dataclass
class BlockNode(GraphNode):
    order: int                 # Display order (separate from identity)
    block_type: BlockType      # Paragraph | Heading | Table | List | Figure | ...
    container_id: int | None   # Owning container (Table, List, Document)
    region_id: int | None      # Semantic region this block belongs to
    features: BlockFeatures    # Lazily computed features
```

### Block Types

Paragraph variants (heading, caption, reference, TOC entry) differ only in **role**, not structure. They use a `ParagraphRole` enum on `ParagraphBlock` rather than subclassing — this avoids dozens of near-empty subclasses. Subclasses are reserved for structurally different blocks (`TableBlock`, `FigureBlock`, `ListBlock`, `CodeBlock`).

Every node lives exactly once in `graph._node_index`. Composite blocks (`TableCell`, `ListItem`) reference children by integer IDs rather than containing actual `BlockNode` objects — eliminating duplicate ownership.

```python
class ParagraphRole(Enum):
    BODY = "body"
    HEADING = "heading"
    CAPTION = "caption"
    REFERENCE = "reference"
    TOC_ENTRY = "toc_entry"
    ABSTRACT = "abstract"
    TITLE = "title"
    METADATA = "metadata"
    AUTHOR = "author"
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"

@dataclass
class ParagraphBlock(BlockNode):
    text: str
    runs: list[Run]            # Inline AST
    role: ParagraphRole        # Semantic role (classified, not parsed)
    heading_level: int | None  # 1-6 if role == HEADING
    style_name: str
    style_base: str | None
    style_hierarchy: list[str]
    is_visual_blank: bool
    is_hidden: bool
    outline_level: int | None
    is_list_item: bool
    list_level: int | None
    list_id: str | None
    numbering_format: str | None
    in_table: bool
    page_break_before: bool
    page_break_after: bool
    section_break_type: str | None
    space_before: float | None
    space_after: float | None

@dataclass
class TableBlock(BlockNode):
    rows: list[TableRow]

@dataclass
class TableRow:
    cells: list[TableCell]

@dataclass
class TableCell:
    child_ids: list[int]       # BlockNode IDs (live in graph._node_index)
    container_id: int          # Owning TableBlock

@dataclass
class ListBlock(BlockNode):
    items: list[ListItem]
    list_type: str             # "ordered" | "bullet" | "checklist"

@dataclass
class ListItem:
    child_ids: list[int]       # BlockNode IDs (live in graph._node_index)
    container_id: int          # Owning ListBlock

@dataclass
class FigureBlock(BlockNode):
    caption: str | None
    image_ref: str | None

@dataclass
class EquationBlock(BlockNode):
    latex: str | None
    mathml: str | None

@dataclass
class CodeBlock(BlockNode):
    code: str
    language: str | None

@dataclass
class PageBreak(BlockNode):
    pass

@dataclass
class SectionBreak(BlockNode):
    break_type: str            # "next_page" | "continuous" | "even_page" | "odd_page"
```

### Inline AST (Run)

Each `Run` has an `id` for precise diagnostic targeting (offsets, annotations, rewrites).

```python
@dataclass
class Run:
    id: int                    # Per-paragraph sequential ID
    type: RunType              # Text | Bold | Italic | Citation | Hyperlink | FootnoteRef | Math | Field
    text: str
    bold: bool
    italic: bool
    font_size: float | None
    font_name: str | None
    color: str | None
    is_hidden: bool

# Specialized run types
@dataclass
class CitationInline(Run):
    raw: str                   # "(Smith, 2020)" or "[1]"
    citations: list[str]       # Parsed citation keys

@dataclass
class HyperlinkInline(Run):
    url: str
    tooltip: str | None

@dataclass
class FootnoteRefInline(Run):
    footnote_id: int

@dataclass
class FieldInline(Run):
    field_type: str            # "PAGE" | "DATE" | "TOC" | "AUTHOR"
```

### RegionNode

Regions are graph nodes, just like blocks. This allows edges to connect blocks to regions, regions to regions (nesting), and regions to reference entries.

```python
@dataclass
class RegionNode(GraphNode):
    type: RegionType           # COVER | TITLE_PAGE | ABSTRACT | TOC | BODY | REFERENCES | APPENDIX | FOOTNOTES | ENDNOTES | TABLES | FIGURES | BACK_MATTER
    label: str | None          # "Appendix A", "Chapter 1 References"
    parent_id: int | None      # Nesting: APPENDIX can contain sub-regions
```

Each block stores its `region_id`. Regions do **not** own blocks — blocks belong to regions.

```python
# Find all blocks in a region
blocks_in_region = [n for n in doc.graph.nodes if isinstance(n, BlockNode) and n.region_id == target_id]
```

### Edge (Relationship Graph)

Edges connect any `GraphNode` — blocks, regions, reference entries, etc. They carry `Provenance` and optional `attributes` for metadata specific to the relationship (e.g., page number, citation index).

```python
@dataclass
class Edge:
    source_id: int             # Any GraphNode ID
    target_id: int             # Any GraphNode ID
    type: EdgeType             # "heading_contains" | "citation_references" | "figure_caption" | "footnote_ref_to" | "toc_targets"
    provenance: Provenance
    attributes: dict | None    # {"page": 5, "citation_index": 2, ...}
```

Edges are **semantic only** — structural relationships (paragraph→next paragraph, block→document) are derived from block order, not stored.

### ReferenceNode

References are graph nodes that connect to classified reference paragraphs via edges. Phase 1 stores `raw_text` only; structured extraction fills fields in later phases.

```python
@dataclass
class ReferenceNode(GraphNode):
    block_id: int              # The ParagraphBlock that triggered this entry (role=REFERENCE)
    raw_text: str

    # Partially extracted fields (Phase 3+)
    authors: list[str] | None
    year: str | None
    title: str | None
    journal: str | None
    publisher: str | None
    doi: str | None
    url: str | None
    pages: str | None
```

### Diagnostic

Diagnostics follow the compiler model (clang, ruff, eslint): severity + rule + message + location + fix. Offsets are **Unicode codepoint** positions to remain editor-agnostic.

```python
@dataclass
class Diagnostic:
    severity: Severity         # error | warning | info | hint
    rule_id: str               # "apa-7.03" | "accessibility-heading"
    message: str
    location: Location | None  # block_id | run_id | region_id
    fix: str | None            # Suggested fix description
    provenance: Provenance

@dataclass
class Location:
    node_id: int               # Any GraphNode ID
    run_id: int | None         # Specific run within a ParagraphBlock
    offset: int | None         # Unicode codepoint offset from block text start
    length: int | None         # Length in Unicode codepoints
```

### Block Features

Features are computed lazily and stored on blocks. Feature extractors register with a registry.

```python
@dataclass
class BlockFeatures:
    lexical: LexicalFeatures | None
    typography: TypographyFeatures | None
    spacing: SpacingFeatures | None
    numbering: NumberingFeatures | None
    language: LanguageInfo | None  # "en" | "fr" | "unknown" (default)

@dataclass
class LexicalFeatures:
    word_count: int
    sentence_count: int
    avg_word_length: float
    vocab_richness: float

@dataclass
class TypographyFeatures:
    font_size: float
    font_name: str
    bold: bool
    italic: bool
    monospace: bool
    all_caps: bool
    small_caps: bool

@dataclass
class SpacingFeatures:
    alignment: str             # "left" | "center" | "right" | "justify"
    first_line_indent: float
    left_indent: float
    right_indent: float
    space_before: float
    space_after: float
    line_spacing: float

@dataclass
class NumberingFeatures:
    outline_level: int | None
    is_list_item: bool
    list_level: int | None
    numbering_format: str | None

@dataclass
class LanguageInfo:
    detected: str              # "en" | "fr" | "unknown"
    confidence: float
```

---

## Pipeline Stages (Detailed)

### Stage 1: Parser

```
Input:  File path or bytes
Output: Document with physical blocks in graph
```

- Each parser is a `Parser` subclass registered by MIME type
- Produces blocks: Paragraph, Heading, Table, List, Figure, PageBreak, SectionBreak
- Parser knows NOTHING about semantics
- Parser advertises capabilities

```python
class Parser(ABC):
    @abstractmethod
    def parse(self, source: str | Path | bytes) -> Document: ...
    
    @property
    @abstractmethod
    def capabilities(self) -> ParserCapabilities: ...
    
    @classmethod
    @abstractmethod
    def supported_mime_types(cls) -> list[str]: ...
```

### Stage 2: Normalizer

```
Input:  DocumentGraph (raw from parser)
Output: DocumentGraph (normalized)
```

- Unicode normalization (NFC)
- Smart quotes → straight quotes
- Non-breaking spaces → regular spaces
- Control characters stripped
- Hidden runs removed (or flagged)
- Adjacent identical runs merged
- Manual line breaks within paragraphs normalized
- `is_visual_blank` computed

### Stage 3: Feature Extraction

```
Input:  DocumentGraph (normalized)
Output: DocumentGraph (with features populated)
```

- Features are computed **lazily** — only when requested
- Feature extractors register with `FeatureRegistry`
- Each extractor declares which block types it handles
- Consumers request features: `doc.get_features(block_id, "typography")`

```python
class FeatureExtractor(ABC):
    name: str
    
    @abstractmethod
    def extract(self, block: Block) -> Any: ...
    
    @classmethod
    @abstractmethod
    def handles_block_type(cls) -> list[BlockType]: ...
```

### Stage 4: Block Classification

```
Input:  DocumentGraph (with features)
Output: DocumentGraph (blocks classified)
```

- Each block gets a `block_type` (if parser didn't assign) and `confidence`
- Paragraph → body? heading? caption? toc? metadata? reference?
- Classifiers are plugin-based

```python
class BlockClassifier(ABC):
    name: str
    
    @abstractmethod
    def classify(self, block: Block, context: DocumentGraph) -> BlockType: ...
```

### Stage 5: Region Builder

```
Input:  DocumentGraph (classified blocks)
Output: DocumentGraph (regions assigned)
```

- State machine: reads classified blocks, determines region boundaries
- Region types: COVER, TITLE_PAGE, ABSTRACT, TOC, BODY, REFERENCES, APPENDIX, FOOTNOTES, ENDNOTES, TABLES, FIGURES, BACK_MATTER
- Each block gets `region_id` assigned
- Regions have confidence + evidence based on boundary signals

### Stage 6: Relationship Resolver

```
Input:  DocumentGraph (regioned)
Output: DocumentGraph (edges added)
```

- Adds permanent edges:
  - Heading → Section (heading_contains)
  - Citation → ReferenceNode (citation_references)
  - Figure → Caption (figure_caption)
  - FootnoteRef → Footnote (footnote_ref_to)
  - TOCEntry → Heading (toc_targets)

### Stage 7: Format Detection (Phase 2)

### Stage 8: Validation / Rule Engine (Phase 2+)

### Stage 9: Exporters

---

## Plugin Architecture

### Registry Pattern

```python
class ParserRegistry:
    _parsers: dict[str, type[Parser]]
    
    def register(self, mime_type: str, parser: type[Parser]): ...
    def get(self, mime_type: str) -> Parser: ...
    def detect(self, source: str | Path) -> Parser: ...  # by extension or magic bytes

class FeatureRegistry:
    _extractors: dict[str, type[FeatureExtractor]]
    
    def register(self, extractor: type[FeatureExtractor]): ...
    def get(self, name: str) -> FeatureExtractor: ...

class ClassifierRegistry:
    _classifiers: dict[str, type[BlockClassifier]]
    
    def register(self, name: str, classifier: type[BlockClassifier]): ...
```

### Rule → RuleResult

Rules return a `RuleResult` rather than a flat list, enabling multi-diagnostic rules, statistical output, and rule-level metadata.

```python
class Rule(ABC):
    @abstractmethod
    def evaluate(self, document: Document) -> RuleResult: ...

@dataclass
class RuleResult:
    rule_id: str
    diagnostics: list[Diagnostic]
    severity_counts: dict[Severity, int]  # Derived from diagnostics
    metadata: dict | None                 # Optional: statistics, timing, etc.
```

### Detection vs Extraction

- **Detection**: "Is this block a citation?" (binary + confidence)
- **Extraction**: "What DOI/authors/year does this citation contain?" (structured data)

These are separate stages with separate plugins.

---

## Visitor / Query API

The primary consumer-facing API. Everything is traversable from the graph without knowing internals.

```python
# Walk all blocks recursively (depth-first)
for block in doc.walk():
    ...

# Typed queries
doc.find(ParagraphBlock, role="heading")  # First heading
doc.find_all(ParagraphBlock)            # All paragraphs
doc.find_all(lambda b: b.region_id == 3)  # Custom filter
doc.find(RegionNode, type="APPENDIX")   # By attribute

# Graph traversal
doc.successors(node_id)                 # Nodes this node connects to
doc.predecessors(node_id)               # Nodes connecting to this node
doc.get_node(node_id)                   # Any GraphNode by ID
doc.edges_from(node_id)                 # Edges originating from node
```

These are convenience methods over the underlying graph — they work for any node type.

---

## Pipeline Stage Rules

1. **Pure stages.** Each stage takes a `Document` and returns a new `Document`. The previous stage is never mutated.
2. **Copy-on-write.** Only changed nodes are replaced; unchanged nodes are shared between stages. This gives immutability without excessive copying.
3. **Reversible.** A stage can be skipped if its input already satisfies the output contract (e.g., re-running features on an already-enriched graph).

```python
# Example: running stages independently
doc1 = parser.parse("paper.docx")
doc2 = normalizer.normalize(doc1)
doc3 = feature_extractor.extract(doc2)
# doc1, doc2, doc3 all valid Document instances
```

---

## Document ID

```python
DocumentId(
    document_id="sha256:e3b0c44298fc1c14...",  # stable content hash
    instance_id="550e8400-e29b-41d4-a716-446655440000"  # per-run UUID
)
```

- `document_id` = SHA-256 of **normalized** document content
  - NOT raw bytes (DOCX is a ZIP with unstable metadata)
  - Normalization: extract paragraph text, style names, headings, tables, lists, images, footnotes — in document order
  - Ignore: timestamps, author metadata, revision IDs, ZIP ordering, temporary XML IDs
- `instance_id` = random UUID, regenerated per parse session

Future: `version_id` for version comparison, `parent_document_id` for forks.

---

## 25 Edge Cases (Mapped to New Model)

The original 25 edge cases still apply. They now map to specific fields on the block model:

| # | Edge case | Model field |
|---|-----------|-------------|
| 1 | Blank ≠ empty | `Paragraph.is_visual_blank` |
| 2 | Page breaks | `Paragraph.page_break_before`, `.page_break_after` |
| 3 | Section breaks | `Paragraph.section_break_type` (or `SectionBreak` block) |
| 4 | Paragraph spacing | `Paragraph.space_before`, `.space_after` |
| 5 | Style inheritance | `Paragraph.style_base`, `.style_hierarchy` |
| 6 | Outline levels | `Paragraph.outline_level`, `.numbering` |
| 7 | Lists via numbering | `List` block type + `Paragraph.list_id`, `.list_level` |
| 8 | Tables | `Table` block type (cells contain blocks) |
| 9 | Captions | Classifier joins caption blocks, Figure.caption |
| 10 | Headers/footers | Parser segregates (stored separately) |
| 11 | Text boxes | Parser segregates into separate blocks |
| 12 | Shapes | Parser segregates (ignored or stored as Figure) |
| 13 | Footnotes | `FootnoteRefInline` run type + separate blocks |
| 14 | Endnotes | Similar to footnotes |
| 15 | Comments | Parser ignores unless requested |
| 16 | Track Changes | Parser option: accept/reject changes |
| 17 | Hidden text | `Run.is_hidden` — filtered in normalizer |
| 18 | Fields | `FieldInline` run type |
| 19 | TOC region | `RegionType.TOC` |
| 20 | Multiple reference sections | Nested regions with labels |
| 21 | Appendices | `RegionType.APPENDIX` |
| 22 | Expanded region types | 13 region types in RegionType enum |
| 23 | PDF abstraction | Parser adapter interface |
| 24 | Confidence | `confidence` on Block, Region, Edge, Diagnostic |
| 25 | Parser ≠ semantic | Pipeline separation — parser never classifies |

---

## Directory Structure

```
tools/docstructure/
├── __init__.py
├── __main__.py                    # CLI entry
│
├── core/                          # Data models (language-neutral)
│   ├── __init__.py
│   ├── document.py                # Document, DocumentId
│   ├── blocks.py                  # Block, Paragraph, Heading, Table, List, Figure, etc.
│   ├── inline.py                  # Run, Text, Bold, Italic, Citation, Hyperlink, etc.
│   ├── region.py                  # Region, RegionType
│   ├── edge.py                    # Edge, EdgeType
│   ├── reference.py               # ReferenceNode
│   ├── diagnostic.py              # Diagnostic, Severity, Location
│   ├── features.py                # BlockFeatures, all feature dataclasses
│   └── base.py                    # Provenance, DocumentId
│
├── parser/                        # Format adapters
│   ├── __init__.py                # ParserRegistry + auto-discover
│   ├── base.py                    # Parser ABC, ParserCapabilities
│   ├── docx.py                    # DOCX → physical blocks
│   └── ...                        # pdf.py, md.py, html.py (future)
│
├── normalizer/
│   ├── __init__.py
│   ├── normalize.py               # Unicode, whitespace, runs, hidden text
│   └── blank.py                   # is_visual_blank detection
│
├── features/                      # Feature extractors (plugin-based)
│   ├── __init__.py                # FeatureRegistry
│   ├── base.py                    # FeatureExtractor ABC
│   ├── typography.py
│   ├── lexical.py
│   ├── spacing.py
│   └── numbering.py
│
├── classifier/                    # Block classifiers (plugin-based)
│   ├── __init__.py                # ClassifierRegistry
│   ├── base.py                    # BlockClassifier ABC
│   ├── paragraph.py               # Score functions → block types
│   └── sections.py                # State machine → regions
│
├── graph/                         # Relationship resolution
│   ├── __init__.py
│   └── resolver.py                # Edge builder
│
├── validate/                      # Validation (Phase 1: interfaces only)
│   ├── __init__.py
│   ├── base.py                    # Rule ABC, RuleEngine ABC
│   ├── diagnostic.py              # Diagnostic builder helpers
│   └── rules/                     # Demo rules (Phase 1: 2-5 skeleton rules)
│       └── __init__.py
│
├── output/                        # Exporters
│   ├── __init__.py
│   ├── json.py                    # Language-neutral JSON export
│   ├── report.py                  # Terminal report
│   └── schema/                    # JSON schemas
│       └── v1.json
│
├── tests/
│   ├── fixtures/                  # Test documents
│   ├── test_parser.py
│   ├── test_normalizer.py
│   ├── test_features.py
│   ├── test_classifier.py
│   ├── test_regions.py
│   ├── test_graph.py
│   ├── test_export.py
│   └── test_edge_cases.py         # One test per edge case
│
└── config.py                      # Default registrations, pipeline wiring
```

---

## JSON Schema (Language-Neutral Contract)

Schema versions are monolithic (`v1`, `v2`), not semantically versioned. This avoids compatibility questions between minor/patch schema bumps.

```json
{
  "docstructure_version": "v1",
  "document_id": {
    "document_id": "sha256:e3b0c44...",
    "instance_id": "550e8400-..."
  },
  "metadata": {
    "ast_version": "docstructure/v1",
    "parser_version": "docx/1.0",
    "source": "paper.docx",
    "language": "en",
    "language_confidence": 0.85
  },
  "graph": {
    "nodes": [
    {
      "id": 1,
      "node_type": "heading",
      "order": 0,
      "region_id": 3,
      "provenance": {
        "confidence": 0.98,
        "produced_by": "heading_classifier/v1",
        "version": "1.0",
        "evidence": ["centered", "bold", "size_14"]
      },
      "level": 1,
      "text": "Introduction",
      "runs": [
        {"type": "text", "text": "Introduction", "bold": false}
      ],
      "features": {
        "typography": {
          "font_size": 14.0,
          "bold": true,
          "centered": true
        }
      }
    },
    {
      "id": 2,
      "node_type": "paragraph",
      "order": 1,
      "region_id": 3,
      "provenance": {
        "confidence": 0.95,
        "produced_by": "paragraph_classifier/v1",
        "version": "1.0",
        "evidence": []
      },
      "is_visual_blank": false,
      "page_break_before": false,
      "text": "Artificial intelligence has transformed...",
      "runs": [
        {"type": "text", "text": "Artificial intelligence has transformed..."},
        {"type": "citation", "text": "(Smith, 2020)", "citations": ["Smith2020"]}
      ],
      "features": {
        "lexical": {"word_count": 24, "sentence_count": 2}
      }
    }
  ],
    ],
    "edges": [
      {
        "source_id": 1,
        "target_id": 3,
        "type": "heading_contains",
        "provenance": {
          "confidence": 0.99,
          "produced_by": "relationship_resolver/v1",
          "version": "1.0",
          "evidence": []
        },
        "attributes": null
      }
    ]
  },
  "analysis": {
    "references": [
      {
        "id": 1,
        "block_id": 42,
        "raw_text": "Smith, J. (2020). AI in Education...",
        "provenance": {
          "confidence": 0.95,
          "produced_by": "reference_extractor/v1",
          "version": "1.0",
          "evidence": []
        },
        "authors": ["Smith, J."],
        "year": "2020",
        "title": "AI in Education",
        "doi": null
      }
    ],
    "diagnostics": [
      {
        "severity": "warning",
        "rule_id": "heading-levels",
        "message": "Heading level jumps from 1 to 3",
        "location": {"node_id": 17, "run_id": null, "offset": null, "length": null},
        "provenance": {
          "confidence": 0.85,
          "produced_by": "heading_validator/v1",
          "version": "1.0",
          "evidence": []
        }
      }
    ]
  }
}
```

---

## Phase Plan

### Phase 1 — Core Engine (this build)

**Goal:** Parse DOCX → DocumentGraph → JSON. CLI working with classification + regions.

| Layer | Scope |
|-------|-------|
| `core/` | All data models: Document, GraphNode, BlockNode, RegionNode, Edge, ReferenceNode, Diagnostic, features |
| `parser/docx.py` | DOCX → physical blocks (ParagraphBlock, TableBlock, ListBlock, FigureBlock, PageBreak, SectionBreak). Parser assigns `block_type`, NOT role. Handles edge cases #1-#18. |
| `normalizer/` | Unicode normalization, run merging, hidden text filtering, `is_visual_blank` |
| `features/` | 4 core extractors: typography, lexical, spacing, numbering. Lazy evaluation. |
| `classifier/paragraph.py` | Paragraph role classification (body, heading, caption, toc, reference, metadata, abstract) |
| `classifier/sections.py` | Region builder state machine (13 region types) |
| `graph/resolver.py` | Basic relationship edges (heading→section, figure→caption) |
| `validate/` | Interfaces only: Rule ABC, Diagnostic model. 2-3 skeleton demo rules. |
| `output/json.py` | JSON export matching schema |
| `__main__.py` | CLI with subcommands |
| `schema/v1.json` | JSON schema (the API contract) |

**CLI:**

```bash
docstructure analyze paper.docx             # graph summary (stderr)
docstructure analyze paper.docx --json      # JSON graph (stdout)
docstructure graph paper.docx               # JSON only (for piped usage)
docstructure graph paper.docx -o out.json
docstructure --help
```

**API:**

```python
from docstructure import open_doc
from docstructure.core.blocks import ParagraphRole

doc = open_doc("paper.docx")

# Graph — single source of truth is nodes
doc.graph.nodes              # All GraphNodes (derived from _node_index)
doc.graph.blocks             # @property view filtered to BlockNode
doc.graph.regions            # @property view filtered to RegionNode
doc.graph.get_node(42)       # O(1) from _node_index cache
doc.graph.edges_from(42)     # Edges originating from node 42

# Analysis
doc.analysis.diagnostics     # Validation diagnostics
doc.analysis.references      # Structured reference entries

# Metadata
doc.metadata.ast_version
doc.metadata.parser_version
doc.metadata.language

# Query API
doc.find(ParagraphBlock, role=ParagraphRole.HEADING)   # First heading
doc.find_all(ParagraphBlock)                             # All paragraphs
doc.find_all(lambda n: n.region_id == 3)                 # Custom filter
doc.walk()                                                # Depth-first traversal
doc.successors(42)                                        # Nodes connected from 42

# Export
doc.to_json()              # dict matching v1 schema
```

**Dependencies:**
- `python-docx` (already in tools/requirements.txt)
- `rich` (already present)
- `jsonschema` (for tests)

**Files to create (Phase 1):**

```
tools/docstructure/__init__.py
tools/docstructure/__main__.py
tools/docstructure/config.py
tools/docstructure/core/__init__.py
tools/docstructure/core/document.py
tools/docstructure/core/blocks.py
tools/docstructure/core/inline.py
tools/docstructure/core/region.py
tools/docstructure/core/edge.py
tools/docstructure/core/reference.py
tools/docstructure/core/diagnostic.py
tools/docstructure/core/features.py
tools/docstructure/core/base.py
tools/docstructure/parser/__init__.py
tools/docstructure/parser/base.py
tools/docstructure/parser/docx.py
tools/docstructure/normalizer/__init__.py
tools/docstructure/normalizer/normalize.py
tools/docstructure/normalizer/blank.py
tools/docstructure/features/__init__.py
tools/docstructure/features/base.py
tools/docstructure/features/typography.py
tools/docstructure/features/lexical.py
tools/docstructure/features/spacing.py
tools/docstructure/features/numbering.py
tools/docstructure/classifier/__init__.py
tools/docstructure/classifier/base.py
tools/docstructure/classifier/paragraph.py
tools/docstructure/classifier/sections.py
tools/docstructure/graph/__init__.py
tools/docstructure/graph/resolver.py
tools/docstructure/validate/__init__.py
tools/docstructure/validate/base.py
tools/docstructure/validate/diagnostic.py
tools/docstructure/validate/rules/__init__.py
tools/docstructure/output/__init__.py
tools/docstructure/output/json.py
tools/docstructure/output/schema/v1.json
tools/docstructure/tests/__init__.py
tools/docstructure/tests/fixtures/  (directory)
```

### Phase 2 — Format Detection + Validation

- `formats/` directory: APA, MLA, IEEE detectors (plugin-based)
- `validate/rules/` — full rule sets for each format
- RuleEngine implementation
- CLI: `detect`, `validate` subcommands
- Format detection runs ALL plugins, returns sorted scores

### Phase 3 — acewriter Integration

- Compatibility shim replacing acewriter's `analyzer.py`
- Remove acewriter dead code (budget.py, rewrite.py, browser.py, etc.)
- docstructure becomes acewriter's detection backend

### Phase 4 — More Parsers

- PDF (via adapter, layout extraction, coordinates, OCR)
- Markdown (headings → structure, code blocks, lists)
- HTML (`<section>`, `<article>`, `<h1>`–`<h6>`, semantic elements)
- ODT (XML-based, similar to DOCX)

### Phase 5 — Multi-Platform

- pip package (`pyproject.toml`)
- npm package (thin wrapper around Python CLI)
- REST API (FastAPI)
- VS Code extension

---

## Existing Logic Analysis — acewriter `analyzer.py`

### What extracts cleanly into the new model

| Component | acewriter location | Extraction target |
|-----------|-------------------|-------------------|
| Paragraph extraction | `_build_paragraph_info()` | `parser/docx.py` → `Paragraph` blocks |
| Heading detection | `_detect_headings()` | `classifier/paragraph.py` |
| Feature extraction | `_extract_features()` | `features/typography.py`, `features/lexical.py` |
| Score functions | `_score_body_v4()` etc. | `classifier/paragraph.py` |
| State machine | `_state_machine()` | `classifier/sections.py` → Region builder |
| Main entry | `detect_structure()` | `parser/docx.parse()` → full pipeline |

### What gets left behind

- `ParagraphInfo` → replaced by `ParagraphBlock(role=ParagraphRole)`
- Integer paragraph indexes → `BlockNode.id` (stable) + `BlockNode.order` (display)
- No table/list models → `TableBlock`, `ListBlock` with `child_ids` references
- No inline models → `Run` / inline AST with `run_id`
- Hardcoded "References", "Student Name" → feature-based classification
- Duplicate `ParagraphScores` → replaced by `Provenance` + `ParagraphRole`
- Dead `ParagraphScore` class → removed entirely

### Gaps from acewriter that docstructure must NOT inherit

1. No `is_visual_blank` → model has it
2. No page/section break tracking → `Paragraph` fields
3. No style inheritance chain → `style_base`, `style_hierarchy`
4. No outline levels → `outline_level` field
5. List detection via bullet chars → `List` block type + numbering
6. No header/footer segregation → parser segregates
7. No text box/shape filtering → parser segregates
8. No footnotes/endnotes regions → `RegionType.FOOTNOTES`, `RegionType.ENDNOTES`
9. No TOC region → `RegionType.TOC`
10. No appendix region → `RegionType.APPENDIX`
11. No expanded region types → 13 region types
12. No inline AST → `Run` types
13. No relationship graph → `Edge` model
14. No reference entries → `ReferenceNode` model
15. Structured references merged with body → separate extraction
16. Duplicate `ParagraphScores` class → single source of truth
17. Dead `ParagraphScore` class → removed

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Over-engineering** the plugin system before real users | Ship with built-in extractors/classifiers. Plugin interface is there but unused until Phase 2-3. |
| **Performance** of immutable stages on large docs | Immutability via copy-on-write for blocks that change. Most stages don't need deep copies. |
| **Composite blocks** (Table, List) complicate traversal | `doc.walk()` handles recursion. `container_id` on every block enables upward navigation. |
| **Content-derived document ID** is complex to compute | Start with randomized `instance_id` only. Add `document_id` when caching is needed (Phase 3). |
| **Edge case gaps** from acewriter carryover | All 25 edge cases explicitly mapped to model fields. Unit tests for each. |
| **Blank paragraph misclassification** | `is_visual_blank` checks tabs, spaces, NBSP, hidden text, manual line breaks. |
| **List detection via bullet chars** | Always use numbering definition from DOCX XML. Never match on "•", "-", "*". |
| **Header/footer leaking into body** | Parser explicitly collects headers/footers from `doc.sections[].header/footer`. |
| **Parser capability gaps go unnoticed** | Validators check `parser.capabilities` before making assertions. |

---

## Testing Strategy

| Layer | Approach |
|-------|----------|
| **Models** | Unit tests: construction, serialization, `walk()`, parent traversal |
| **DOCX parser** | Integration against real .docx samples. Edge case tests (#1-#18). |
| **Normalizer** | Tests: Unicode, run merging, hidden text, `is_visual_blank` |
| **Features** | Feature extractor tests. Verify lazy evaluation. |
| **Classifier** | Known-feature → expected-classification tests |
| **Regions** | Known-block-sequences → expected-region tests |
| **Graph edges** | Relationship resolver tests (citation→reference, heading→section) |
| **Export** | JSON output validates against `schema/v1.json`. Round-trip tests. |
| **CLI** | Subprocess tests for all subcommands |
| **Regression** | Same .docx processed by acewriter AND docstructure → same regions |

### Sample documents needed
- APA paper (cover, abstract, body, references, headings)
- MLA paper (header, Works Cited)
- Paper with appendix, footnotes, endnotes
- Paper with TOC, lists, tables, figures, captions
- Paper with hidden text, track changes, fields
- Paper with multiple reference sections
- Document with text boxes, shapes, section breaks
- Document with blank/near-blank paragraphs
- Business report (no academic format)

---

## What Phase 1 explicitly defers

| Feature | Why deferred |
|---------|--------------|
| PDF parser | Extremely hard (layout, coordinates, OCR). Needs adapter design. Phase 4. |
| Markdown/HTML parsers | Simple but not needed yet. Phase 4. |
| Format detection (APA/MLA) | Phase 2. Phase 1 answers "what is this document?" not "what format?" |
| Full RuleEngine | Interfaces only in Phase 1. Engine + rules in Phase 2. |
| Advanced relationship resolution | Phase 2. Phase 1 does basic heading→section, citation→reference. |
| Rich reference extraction | Phase 3. Phase 1 stores `raw_text` only. |
| Caching layer | Phase 3. Not needed until acewriter integration. |
| Incremental parsing | Phase 5. Architecture supports it via Block.ID stability. |
| Language detection | Phase 3. Phase 1 defaults to `"unknown"`. |
| Page layout / coordinate model | Phase 4. Needed for PDF. |

---

## Success Criteria for Phase 1

```bash
# 0. Schema exists
ls docstructure/output/schema/v1.json

# 1. Parse a real .docx
docstructure analyze sample.docx --json > graph.json

# 2. JSON validates against schema
python3 -c "
import json, jsonschema
schema = json.load(open('docstructure/output/schema/v1.json'))
data = json.load(open('graph.json'))
jsonschema.validate(data, schema)
"

# 3. Output has expected shape
python3 -c "
d = json.load(open('graph.json'))
assert 'graph' in d
assert 'analysis' in d
assert 'metadata' in d
assert 'nodes' in d['graph']
assert 'edges' in d['graph']
assert len(d['graph']['nodes']) > 0
assert d['graph']['nodes'][0]['id']  # stable integer ID
assert d['graph']['nodes'][0]['order'] is not None
assert d['graph']['nodes'][0]['provenance']  # shared Provenance
"

# 4. Edge cases handled
python3 -m pytest tests/test_edge_cases.py -v

# 5. Regions match acewriter (on compatible docs)
python3 -c "
from acewriter.lib.document.docx.analyzer import detect_structure
# ... compare regions for docs that don't use new features
"

# 6. CLI works
docstructure analyze sample.docx
docstructure analyze sample.docx --json
docstructure graph sample.docx
docstructure graph sample.docx -o out.json
docstructure --help

# 7. Basic graph features work
python3 -c "
from docstructure import open_doc
doc = open_doc('sample.docx')
print(f'{len(doc.graph.nodes)} nodes, {len(doc.graph.edges)} edges, {len(doc.analysis.diagnostics)} diagnostics')
assert doc.graph.get_node(1) is not None
assert doc.find(ParagraphBlock, role='body') is not None
assert doc.find_all(lambda n: n.region_id == 1) is not None
"
```
