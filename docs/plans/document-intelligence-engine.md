# Document Intelligence Engine — Implementation Plan

## Overview

Replace `detect_body_range()` with a **Document Intelligence Engine** that answers: *"What kind of paragraph is this?"* Built as pure infrastructure — the analyzer describes the document, rewrite policy decides what to do with it.

**Target:** ~1000-1200 lines across `analyzer.py` + `rewrite.py` + tests. Rule-based, no ML.

## Architecture: Five Phases

```
Phase 1 — Paragraph Extraction
    docx_doc → ParagraphInfo[]

Phase 2 — Heading Detection
    ParagraphInfo[] → Heading[]

Phase 3 — Region Detection
    Heading[] + ParagraphInfo[] → DocumentStructure

Phase 4 — Rewrite Policy (separate layer)
    DocumentStructure + AcademicPolicy → RewritePlan

Phase 5 — Humanizer
    RewritePlan → rewritten document
```

Each phase is independently testable. The analyzer (Phases 1-3) never knows what "humanize" means.

---

## File Structure

```
humanize/lib/document/docx/
├── __init__.py
├── analyzer.py          # NEW: Phases 1-3 (~900 lines)
├── reader.py            # existing (unchanged)
├── structure.py         # existing (keep for backward compat)
└── writer.py            # existing (unchanged)

humanize/lib/
├── rewrite.py           # NEW: RewritePolicy + AcademicRewritePolicy (~150 lines)
├── commands.py          # existing (update callsites)
└── ...                  # existing files unchanged

humanize/tests/
├── __init__.py
├── fixtures/
│   ├── __init__.py
│   └── ... (synthetic DOCX files)
├── test_analyzer.py     # NEW (~500 lines)
└── test_rewrite.py      # NEW (~100 lines)
```

---

## Data Model

### Enums

```python
from dataclasses import dataclass, field
from enum import Enum


class ParagraphClass(Enum):
    """What kind of paragraph is this? Every paragraph gets exactly one."""
    # Structural
    TITLE = "title"
    SUBTITLE = "subtitle"
    HEADING = "heading"           # any level
    SUBHEADING = "subheading"     # distinct from heading when needed

    # Content
    BODY = "body"
    QUOTE = "quote"
    LIST = "list"

    # Non-text
    TABLE = "table"
    TABLE_CELL = "table_cell"
    CAPTION = "caption"
    CODE = "code"
    INLINE_CODE = "inline_code"
    EQUATION = "equation"

    # References
    REFERENCE = "reference"       # a single citation entry

    # Front/Back matter
    COVER_FIELD = "cover_field"   # name, course, instructor on cover
    TOC_ENTRY = "toc_entry"       # "Introduction........3"

    # Marginalia
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_NUMBER = "page_number"

    # Catch-all
    BLANK = "blank"


class RegionType(Enum):
    """Document regions. Expanded for future-proofing."""
    COVER = "cover"
    ABSTRACT = "abstract"
    EXECUTIVE_SUMMARY = "executive_summary"
    TOC = "toc"
    LIST_OF_FIGURES = "list_of_figures"
    LIST_OF_TABLES = "list_of_tables"
    LIST_OF_ALGORITHMS = "list_of_algorithms"
    LIST_OF_LISTINGS = "list_of_listings"
    PREFACE = "preface"
    FOREWORD = "foreword"
    FRONT_MATTER = "front_matter"     # container
    BODY = "body"
    GLOSSARY = "GLOSSARY"
    REFERENCES = "references"
    BIBLIOGRAPHY = "bibliography"
    ACKNOWLEDGEMENTS = "acknowledgements"
    APPENDIX = "appendix"
    INDEX = "index"
    BACK_MATTER = "back_matter"       # container


class CitationStyle(Enum):
    APA = "apa"
    MLA = "mla"
    IEEE = "ieee"
    AMA = "ama"
    CHICAGO = "chicago"
    HARVARD = "harvard"
    UNKNOWN = "unknown"
```

### Data Classes

```python
@dataclass
class Signal:
    """A single piece of evidence for a detection decision."""
    name: str       # e.g. "heading", "citation_density", "doi"
    score: int      # contribution to total score, e.g. +5


@dataclass
class Heading:
    """A detected heading."""
    level: int
    paragraph_idx: int
    text: str
    style_name: str


@dataclass
class ParagraphInfo:
    """Metadata for every paragraph — computed once, used everywhere."""
    index: int
    text: str
    style_name: str
    centered: bool
    bold: bool
    font_size: float | None
    word_count: int
    char_count: int
    has_page_break: bool
    # Set later by classification
    paragraph_class: ParagraphClass = ParagraphClass.BODY


@dataclass
class Region:
    """A detected document region. Purely descriptive — no rewrite logic."""
    type: RegionType
    start: int              # paragraph index (inclusive)
    end: int                # paragraph index (exclusive)
    confidence: int         # 0-100 (percentage)
    signals: list[Signal]   # evidence that produced this detection
    children: list['Region'] = field(default_factory=list)


@dataclass
class DocumentStructure:
    """Complete analysis. The single return value of the analyzer."""
    regions: list[Region]
    headings: list[Heading]
    paragraphs: list[ParagraphInfo]
    body_range: tuple[int, int]   # convenience: (start, end) of BODY

    def statistics(self) -> 'DocumentStatistics':
        """Derived — computed on demand, never stored stale."""
        return compute_statistics(self)


@dataclass
class DocumentStatistics:
    """Computed from DocumentStructure, not stored separately."""
    paragraphs: int
    headings: int
    tables: int
    figures: int
    code_blocks: int
    equations: int
    reference_entries: int
    appendices: int
    detected_citation_style: CitationStyle
    bibliography_dois: int
    bibliography_urls: int
    bibliography_years: int
```

---

## Phase 1: Paragraph Extraction (~70 lines)

```python
def _build_paragraph_info(docx_doc) -> list[ParagraphInfo]:
```

Single pass over `docx_doc.paragraphs`. For each paragraph, extract:

| Field | Source |
|-------|--------|
| `style_name` | `p.style.name` |
| `centered` | alignment == CENTER |
| `bold` | all non-empty runs are bold |
| `font_size` | first run's font size (pt) |
| `word_count` | `len(p.text.split())` |
| `char_count` | `len(p.text)` |
| `has_page_break` | XML: `<w:br w:type="page"/>` or `<w:lastRenderedPageBreak/>` |

**Why not reuse `reader.py`:** Reader builds `dict` objects for the full Document model. `ParagraphInfo` is a lightweight dataclass for analysis. Independent construction avoids coupling.

**Page break detection** (~10 lines):
```python
def _has_page_break(p) -> bool:
    """Check paragraph XML for page break elements."""
    for child in p._element:
        if child.tag.endswith('}r'):
            for br in child.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br'):
                if br.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type') == 'page':
                    return True
        if child.tag.endswith('}lastRenderedPageBreak'):
            return True
    return False
```

---

## Phase 2: Heading Detection (~90 lines)

```python
def _detect_headings(paras: list[ParagraphInfo]) -> list[Heading]:
```

**Scoring:**

| Signal | Score |
|--------|-------|
| Style name contains "heading" | +5 |
| Style name is "Title" or "Subtitle" | +3 (classify as heading, not TOC) |
| All non-empty runs bold, text < 60 chars | +3 |
| Text is a known section name | +2 |
| Text is numbered (1., 1.1, I., Chapter N) | +2 |
| Followed by body-length text (not another heading) | +1 |

**Threshold:** score >= 5 → heading.

**Level inference:**
- Style "Heading 1" → level 1, "Heading 2" → level 2, etc.
- Numbered: `1.` → level 1, `1.1` → level 2, `1.1.1` → level 3
- Bold + short → level 1 (default assumption)

**Known section names:**
```python
SECTION_NAMES = {
    "introduction", "background", "literature review", "related work",
    "methodology", "methods", "method", "approach",
    "results", "findings", "analysis",
    "discussion",
    "conclusion", "conclusions", "summary",
    "abstract", "executive summary",
    "references", "bibliography", "works cited",
    "acknowledgements", "acknowledgments",
    "appendix", "appendices",
    "index", "glossary",
    "list of figures", "list of tables", "list of algorithms",
    "list of listings", "table of contents", "contents",
    "preface", "foreword",
}
```

---

## Phase 3: Region Detection (~400 lines)

This is the core. Regions are detected via scoring, then assembled into hierarchy.

### 3a. Cover Detection (~60 lines)

```python
def _detect_cover(paras: list[ParagraphInfo]) -> Region | None:
```

**Scoring:**

| Signal | Score |
|--------|-------|
| Paragraph index == 0 | +3 |
| Title/Subtitle style | +3 |
| Text contains keyword (name, course, instructor, university, date, submitted) | +2 each, max +6 |
| Text is centered | +2 |
| Text is short (< 100 chars) | +1 |
| 3+ consecutive short centered paragraphs in first 10 | +3 |

**Threshold:** score >= 8. End = first paragraph after cluster that's longer or has heading style. Paragraphs inside cover → `ParagraphClass.COVER_FIELD`.

### 3b. Abstract Detection (~50 lines)

```python
def _detect_abstract(paras: list[ParagraphInfo], headings: list[Heading]) -> Region | None:
```

| Signal | Score |
|--------|-------|
| Heading text is "Abstract" or "Executive Summary" | +5 |
| Heading style is Heading 1 or 2 | +2 |
| Appears before first body heading | +2 |
| Section is short (< 500 words) | +1 |
| No sub-headings within section | +1 |

**Threshold:** score >= 7. End = next heading or paragraph gap.

### 3c. TOC Detection (~50 lines)

```python
def _detect_toc(paras: list[ParagraphInfo], headings: list[Heading]) -> Region | None:
```

| Signal | Score |
|--------|-------|
| Heading text matches "Table of Contents" / "Contents" / "TOC" | +5 |
| Style contains "toc" | +4 |
| Text contains dot leaders (`.....`) | +3 |
| Text matches numbered entry with page number | +2 |
| 3+ consecutive TOC-style paragraphs | +2 |

**Threshold:** score >= 5. Paragraphs inside TOC → `ParagraphClass.TOC_ENTRY`.

### 3d. List of Figures/Tables (~30 lines)

```python
def _detect_lists(paras: list[ParagraphInfo], headings: list[Heading]) -> list[Region]:
```

Match headings: "List of Figures", "List of Tables", "List of Illustrations", "List of Algorithms", "List of Listings".

### 3e. References Detection (~100 lines)

```python
def _detect_references(paras: list[ParagraphInfo], headings: list[Heading]) -> Region | None:
```

**Scoring:**

| Signal | Score |
|--------|-------|
| Heading text matches reference markers | +5 |
| Heading style is Heading 1 | +2 |
| Appears after body content | +2 |
| Next paragraphs contain years (1900-2099) | +1 each, max +3 |
| Next paragraphs contain DOI/URL | +1 each, max +2 |
| Hanging indents detected | +2 |
| Citation density > 50% of first 10 paragraphs | +3 |

**Threshold:** score >= 9.

**Citation style classification** (called after references region found):

```python
def _classify_citation_style(paras: list[ParagraphInfo], start: int, end: int) -> CitationStyle:
```

Check first 10 paragraphs:
- **APA:** `Name, I. (Year).` or `Name, I. N., & Name, I. N. (Year).`
- **MLA:** `Name, First. "Title."`
- **IEEE:** `[1]` or `[2]` at start
- **AMA:** `1.` `2.` at start
- **Chicago:** footnote-style superscript numerals
- **Harvard:** `Name (Year)`

**Bibliography quality** (for statistics):

```python
def _analyze_bibliography(paras, start, end) -> dict:
    # Returns: {"entries": N, "dois": N, "urls": N, "years": N}
```

**Key rule:** All paragraphs inside references region become `ParagraphClass.REFERENCE`. The region owns its paragraphs.

### 3f. Appendix Detection (~40 lines)

```python
def _detect_appendices(paras: list[ParagraphInfo], headings: list[Heading]) -> list[Region]:
```

Regex: `Appendix`, `Appendix A`, `Appendix B`, `Appendices`, `Supplementary Material`, `Supplement`.

Each appendix letter/number gets its own sub-region. End = next appendix heading or end of document.

### 3g. Acknowledgements Detection (~25 lines)

```python
def _detect_acknowledgements(paras, headings) -> Region | None:
```

Heading: "Acknowledgements" / "Acknowledgments". Usually straightforward.

### 3h. Index Detection (~15 lines)

```python
def _detect_index(paras, headings) -> Region | None:
```

Heading: "Index". Usually at very end.

### 3i. Preface / Foreword Detection (~20 lines)

```python
def _detect_preface(paras, headings) -> Region | None:
```

Heading: "Preface" / "Foreword". Usually between TOC and body.

### 3j. Glossary Detection (~15 lines)

```python
def _detect_glossary(paras, headings) -> Region | None:
```

Heading: "Glossary". Usually between body and back matter.

### 3k. Body = Complement (~25 lines)

```python
def _detect_body(
    front_matter: list[Region],
    back_matter: list[Region],
    total_paragraphs: int,
) -> Region:
```

**Body = everything not claimed by any other region.** No direct detection. This avoids bugs where we try to find "where body starts" — it's simply the gap between front and back matter.

### 3l. Container Assembly (~40 lines)

```python
def _assemble_containers(
    front_pieces: list[Region],   # cover, abstract, toc, lists, preface, foreword
    back_pieces: list[Region],    # references, appendix, acknowledgements, index, glossary
    total_paragraphs: int,
) -> tuple[Region, Region]:
```

Wraps into `FrontMatter` and `BackMatter` parent regions with `children`. Overlapping regions are merged (e.g., if cover and abstract overlap, take the union).

### 3m. Paragraph Classification (post-region) (~80 lines)

```python
def _classify_paragraphs_after_regions(
    paras: list[ParagraphInfo],
    regions: list[Region],
    headings: list[Heading],
) -> list[ParagraphInfo]:
```

After regions are detected, classify every paragraph:

1. **Blank** — empty or whitespace-only
2. **Heading** — already detected in Phase 2
3. **Cover field** — inside COVER region
4. **TOC entry** — inside TOC region
5. **Reference** — inside REFERENCES region
6. **Table cell** — inside a `<w:tbl>` element
7. **Caption** — starts with "Figure", "Table", "Fig.", "Tab.", short, often italic
8. **Code** — monospace font, high symbol density, or code-like indentation
9. **Equation** — math symbols or style contains "equation"/"math"
10. **List** — bullet chars, numbered patterns, or list style
11. **Title** — Title style
12. **Subtitle** — Subtitle style
13. **Body** — everything else

**Key insight:** References own their paragraphs. Once the REFERENCES region is detected, every paragraph inside it gets `REFERENCE` class — no separate citation pattern matching needed at paragraph level.

---

## Phase 4: Rewrite Policy (~150 lines, separate file)

**File:** `humanize/lib/rewrite.py`

```python
from abc import ABC, abstractmethod


class RewritePolicy(ABC):
    """Decides what to rewrite. Completely separate from analysis."""

    @abstractmethod
    def should_rewrite_region(self, region: Region) -> bool:
        """Should this region be considered for rewriting?"""

    @abstractmethod
    def should_rewrite_paragraph(self, para: ParagraphInfo, region: Region) -> bool:
        """Should this specific paragraph be rewritten?"""


class AcademicRewritePolicy(RewritePolicy):
    """Default policy for academic documents."""

    # Region-level rules
    REGION_REWRITE = {
        RegionType.BODY:              True,
        RegionType.ABSTRACT:          True,
        RegionType.EXECUTIVE_SUMMARY: True,
        RegionType.ACKNOWLEDGEMENTS:  True,
        RegionType.PREFACE:           True,
        RegionType.FOREWORD:          True,
        RegionType.COVER:             False,
        RegionType.TOC:               False,
        RegionType.LIST_OF_FIGURES:   False,
        RegionType.LIST_OF_TABLES:    False,
        RegionType.LIST_OF_ALGORITHMS: False,
        RegionType.LIST_OF_LISTINGS:  False,
        RegionType.REFERENCES:        False,
        RegionType.BIBLIOGRAPHY:      False,
        RegionType.APPENDIX:          False,
        RegionType.INDEX:             False,
        RegionType.GLOSSARY:          False,
    }

    # Paragraph-level exceptions (within rewriteable regions)
    PARAGRAPH_SKIP = {
        ParagraphClass.CODE,
        ParagraphClass.EQUATION,
        ParagraphClass.TABLE,
        ParagraphClass.TABLE_CELL,
        ParagraphClass.CAPTION,
        ParagraphClass.INLINE_CODE,
        ParagraphClass.REFERENCE,
        ParagraphClass.FOOTNOTE,
        ParagraphClass.ENDNOTE,
        ParagraphClass.BLANK,
    }

    def should_rewrite_region(self, region: Region) -> bool:
        return self.REGION_REWRITE.get(region.type, True)

    def should_rewrite_paragraph(self, para: ParagraphInfo, region: Region) -> bool:
        if not self.should_rewrite_region(region):
            return False
        if para.paragraph_class in self.PARAGRAPH_SKIP:
            return False
        return True


class ThesisPolicy(AcademicRewritePolicy):
    """More conservative: skip appendices, preface, foreword."""
    pass


class JournalPolicy(AcademicRewritePolicy):
    """Aggressive: rewrite everything except references and tables."""
    pass
```

### RewritePlan

```python
@dataclass
class RewritePlan:
    """Output of policy applied to structure."""
    paragraphs_to_rewrite: list[int]    # paragraph indices
    paragraphs_to_skip: list[int]       # paragraph indices
    regions_rewritten: list[RegionType] # which regions were targeted

    @classmethod
    def from_structure(
        cls,
        structure: DocumentStructure,
        policy: RewritePolicy,
    ) -> 'RewritePlan':
        """Apply policy to structure. Returns the plan."""
        rewrite = []
        skip = []
        regions = []

        for region in structure.regions:
            if policy.should_rewrite_region(region):
                regions.append(region.type)
                for i in range(region.start, region.end):
                    para = structure.paragraphs[i]
                    if policy.should_rewrite_paragraph(para, region):
                        rewrite.append(i)
                    else:
                        skip.append(i)

        return cls(
            paragraphs_to_rewrite=rewrite,
            paragraphs_to_skip=skip,
            regions_rewritten=regions,
        )
```

### Usage in commands.py

```python
from .document.docx.analyzer import detect_structure
from .rewrite import AcademicRewritePolicy, RewritePlan

structure = detect_structure(docx_doc)
policy = AcademicRewritePolicy()
plan = RewritePlan.from_structure(structure, policy)

# Now iterate:
for idx in plan.paragraphs_to_rewrite:
    # rewrite this paragraph
    ...
```

**Body rewriting is paragraph-based.** Instead of "rewrite BODY region", iterate `plan.paragraphs_to_rewrite` which already excludes code, tables, equations, captions.

---

## Phase 5: Humanizer Integration (~0 new lines in analyzer)

The humanizer doesn't change. `commands.py` uses `RewritePlan` to know which paragraphs to send to the humanizer API.

```python
# In commands.py
structure = detect_structure(docx_doc)
plan = RewritePlan.from_structure(structure, AcademicRewritePolicy())

# Build text from rewriteable paragraphs only
para_texts = []
para_indices = []
for idx in plan.paragraphs_to_rewrite:
    para_texts.append(structure.paragraphs[idx].text)
    para_indices.append(idx)

full_text = "\n\n".join(para_texts)
humanized_text, _ = api_pipeline(full_text, src_name, args)

# Map back and replace
# ... existing logic, but using plan.paragraphs_to_rewrite instead of body range
```

---

## Statistics: Derived, Not Stored

```python
def compute_statistics(structure: DocumentStructure) -> DocumentStatistics:
    """Compute from DocumentStructure. Called on demand, never cached."""
    paras = structure.paragraphs
    regions = structure.regions

    # Count by paragraph class
    tables = sum(1 for p in paras if p.paragraph_class == ParagraphClass.TABLE)
    code_blocks = sum(1 for p in paras if p.paragraph_class == ParagraphClass.CODE)
    equations = sum(1 for p in paras if p.paragraph_class == ParagraphClass.EQUATION)
    figures = sum(1 for p in paras if p.paragraph_class == ParagraphClass.CAPTION
                  and p.text.lower().startswith(("figure", "fig.")))

    # Count by region type
    appendices = sum(1 for r in regions if r.type == RegionType.APPENDIX)
    refs_region = next((r for r in regions if r.type == RegionType.REFERENCES), None)
    ref_entries = (refs_region.end - refs_region.start) if refs_region else 0

    # Citation style + bibliography (from references region)
    citation_style = CitationStyle.UNKNOWN
    dois = urls = years = 0
    if refs_region:
        citation_style = _classify_citation_style(paras, refs_region.start, refs_region.end)
        bib = _analyze_bibliography(paras, refs_region.start, refs_region.end)
        dois, urls, years = bib["dois"], bib["urls"], bib["years"]

    return DocumentStatistics(
        paragraphs=len(paras),
        headings=len(structure.headings),
        tables=tables,
        figures=figures,
        code_blocks=code_blocks,
        equations=equations,
        reference_entries=ref_entries,
        appendices=appendices,
        detected_citation_style=citation_style,
        bibliography_dois=dois,
        bibliography_urls=urls,
        bibliography_years=years,
    )
```

---

## Integration with Existing Code

### Backward Compatibility

`detect_body_range()` in `structure.py` stays **unchanged**. Any code calling it continues to work.

### `commands.py` Changes

**Current** (lines 666, 692, 867, 887):
```python
from .document.docx.structure import detect_body_range
body_start, body_end = detect_body_range(docx_doc)
```

**New:**
```python
from .document.docx.analyzer import detect_structure
from .rewrite import AcademicRewritePolicy, RewritePlan

structure = detect_structure(docx_doc)
body_start, body_end = structure.body_range  # convenience field
```

The `body_range` convenience field means the rest of `commands.py` needs zero changes for basic operation. Paragraph-level skipping is a follow-up enhancement.

### Future Benefits

Once `DocumentStructure` is available, `commands.py` can:
- Skip rewriting code blocks, tables, equations via `RewritePlan`
- Use different policies: `ThesisPolicy`, `JournalPolicy`
- Generate richer reports using `structure.statistics()`
- Export structure JSON for debugging

---

## Debug Output

### `--debug-structure` Flag

Print to stderr:

```
=== Document Structure ===

COVER (88%)
  +3 Title style
  +3 Centered
  +6 Keywords (name, course, instructor)
  +2 Short text
  Paragraphs: 0-7

ABSTRACT (96%)
  +5 Heading "Abstract"
  +2 Heading 1
  +2 Before body
  +1 Short section (< 500 words)
  Paragraphs: 8-12

TOC (94%)
  +5 Heading "Table of Contents"
  +4 TOC style
  +3 Dot leaders
  Paragraphs: 13-27

BODY (100%)
  Paragraphs: 28-147
  (complement of front + back matter)

REFERENCES (97%)
  +5 Heading "References"
  +2 Heading 1
  +3 Citation density
  +2 DOI
  +2 Hanging indent
  +1 Years
  Citation Style: APA
  Entries: 43 | DOIs: 31 | URLs: 7 | Years: 43
  Paragraphs: 148-190

APPENDIX A (99%)
  +5 Heading "Appendix A"
  +5 Appendix regex
  Paragraphs: 191-210

APPENDIX B (99%)
  +5 Heading "Appendix B"
  +5 Appendix regex
  Paragraphs: 211-230

ACKNOWLEDGEMENTS (95%)
  +5 Heading "Acknowledgements"
  +2 Heading 1
  Paragraphs: 231-233

=== Statistics ===
Paragraphs: 234 | Headings: 18 | Tables: 3
Figures: 8 | Code: 2 | Equations: 5
Citation Style: APA
DOIs: 31 | URLs: 7 | Years: 43
```

### `--dump-structure` Flag

Export `DocumentStructure` as JSON to `{stem}.structure.json`.

### `--dump-rewrite-plan` Flag

Export `RewritePlan` as JSON showing which paragraphs will be rewritten/skipped.

---

## Implementation Steps

| # | Step | Lines | Depends on |
|---|------|-------|------------|
| 1 | Create `analyzer.py` with dataclasses | ~80 | — |
| 2 | Phase 1: `_build_paragraph_info()` | ~70 | #1 |
| 3 | Phase 2: `_detect_headings()` | ~90 | #2 |
| 4 | Phase 3a-3i: Individual region detectors | ~350 | #2, #3 |
| 5 | Phase 3j-3l: Body complement + container assembly | ~65 | #4 |
| 6 | Phase 3m: Paragraph classification (post-region) | ~80 | #5 |
| 7 | `detect_structure()` — wire phases together | ~40 | #6 |
| 8 | `compute_statistics()` | ~50 | #7 |
| 9 | Create `rewrite.py` with `AcademicRewritePolicy` + `RewritePlan` | ~150 | #7 |
| 10 | Update `commands.py` — switch to `detect_structure()` + `RewritePlan` | ~30 | #9 |
| 11 | Add CLI flags: `--debug-structure`, `--dump-structure`, `--dump-rewrite-plan` | ~60 | #7, #9 |
| 12 | Unit tests: per-detector in `test_analyzer.py` | ~500 | #7 |
| 13 | Unit tests: `test_rewrite.py` | ~100 | #9 |

**Total:** ~1000-1200 lines (analyzer + rewrite + tests)

---

## Testing Strategy

### Unit Tests Per Detector (`test_analyzer.py`)

```
Phase 1:
  test_build_paragraph_info()
  test_page_break_detection()
  test_bold_detection()
  test_centered_detection()

Phase 2:
  test_detect_headings_from_style()
  test_detect_headings_from_bold()
  test_detect_headings_numbered()
  test_heading_level_inference()

Phase 3:
  test_detect_cover_with_keywords()
  test_detect_cover_no_cover()
  test_detect_abstract_heading()
  test_detect_abstract_no_abstract()
  test_detect_toc_dot_leaders()
  test_detect_toc_no_toc()
  test_detect_references_apa()
  test_detect_references_mla()
  test_detect_references_ieee()
  test_classify_citation_style()
  test_analyze_bibliography()
  test_detect_appendix_single()
  test_detect_appendix_multiple()
  test_detect_acknowledgements()
  test_detect_index()
  test_body_as_complement()
  test_body_no_front_matter()
  test_front_matter_container()
  test_back_matter_container()

Paragraph classification:
  test_classify_code_monospace()
  test_classify_code_symbols()
  test_classify_equation_math()
  test_classify_caption_figure()
  test_classify_caption_table()
  test_classify_list_bullet()
  test_classify_list_numbered()
  test_classify_reference_inside_region()
  test_classify_toc_entry()
  test_classify_cover_field()

Integration:
  test_detect_structure_apa_paper()
  test_detect_structure_no_cover()
  test_detect_structure_no_toc()
  test_detect_structure_multiple_appendices()
```

### Unit Tests for Rewrite (`test_rewrite.py`)

```
test_academic_policy_body_rewriteable()
test_academic_policy_references_not_rewriteable()
test_academic_policy_appendix_not_rewriteable()
test_academic_policy_code_skipped()
test_academic_policy_table_skipped()
test_academic_policy_equation_skipped()
test_academic_policy_caption_skipped()
test_rewrite_plan_from_structure()
test_thesis_policy()
test_journal_policy()
```

### Test Documents (Synthetic DOCX)

- `apa_paper.docx` — Cover + Abstract + TOC + Body + References (APA)
- `mla_paper.docx` — MLA format
- `ieee_paper.docx` — IEEE format, `[1]` references
- `no_cover.docx` — Starts with abstract
- `no_toc.docx` — No table of contents
- `multiple_appendices.docx` — Appendix A, B, C
- `with_code.docx` — Monospace code blocks in body
- `with_equations.docx` — Math content
- `with_figures.docx` — Figure captions
- `thesis.docx` — Full thesis with all front/back matter

### Edge Cases

- No cover page (starts with abstract or body)
- Missing abstract
- Multiple appendices (A, B, C)
- No TOC
- Unconventional heading formatting
- Mixed citation styles
- Very short documents (< 5 pages)
- Very long documents (100+ pages)
- Non-English text (headings still in English)
- PDF-converted DOCX (lost formatting)
- Document with no headings at all
- Document that's entirely body text

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| False positive on cover detection | Threshold tuning; confidence score lets callers decide |
| Heading detection misses custom styles | Bold + short text fallback; scoring-based |
| Citation style misclassification | Return UNKNOWN when ambiguous; don't force |
| Performance on large documents | Single pass for ParagraphInfo; O(n) for everything else |
| Breaking existing `commands.py` flow | `body_range` convenience field; keep `detect_body_range()` alive |
| Statistics become stale | Derived on demand via `statistics()`, never stored |
| Rewrite policy too rigid | Pluggable `RewritePolicy` ABC; `ThesisPolicy`, `JournalPolicy` extend base |

---

## File Structure (Final)

```
humanize/lib/document/docx/
├── __init__.py
├── analyzer.py          # NEW: ~900 lines (Phases 1-3)
├── reader.py            # existing (unchanged)
├── structure.py         # existing (unchanged, backward compat)
└── writer.py            # existing (unchanged)

humanize/lib/
├── rewrite.py           # NEW: ~150 lines (Phase 4)
├── commands.py          # existing (update callsites)
└── ...

humanize/tests/
├── __init__.py
├── fixtures/
│   ├── __init__.py
│   └── ... (10 synthetic DOCX files)
├── test_analyzer.py     # NEW: ~500 lines
└── test_rewrite.py      # NEW: ~100 lines
```
