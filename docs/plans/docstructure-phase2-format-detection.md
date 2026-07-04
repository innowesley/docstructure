# Phase 2: Format Detection + Validation + acewriter Cleanup

**Status:** Completed  
**Target:** `tools/docstructure/` — extend with format detection plugins  
**Related pending tasks:** `v4-cleanup.md` (acewriter analyzer cleanup)

---

## Overview

Build a plugin-based format detection system for docstructure, plus format-specific validation rules. Also clean up acewriter's old analyzer code that's been superseded by docstructure.

### Deliverables

| Component | Description |
|-----------|-------------|
| `formats/` plugin directory | FormatDetector ABC, FormatRegistry, APA/MLA/IEEE detectors |
| Format-scoped validation rules | APA/MLA/IEEE compliance rule sets |
| CLI: `detect` + enhanced `validate` | New subcommands + format-aware validation |
| Schema v2 | Add `format_detection` + `validation` blocks to JSON output |
| v4-cleanup (acewriter) | Remove dead `ParagraphScore`, duplicate `ParagraphScores`, rename `_v4` suffix |
| Integration tests | Golden tests for format detection on real documents |

---

## Existing Logic Analysis

### docstructure Phase 1 — what exists

The current pipeline (`pipeline.py`) runs 5 stages in sequence:
1. **Parse** → `parser/docx.py` produces physical `ParagraphBlock` nodes
2. **Normalize** → `normalizer/normalize.py` cleans text/runs
3. **Features** → `features/__init__.py` computes word/sentence counts
4. **Classify** → `classifier/paragraph.py` assigns `ParagraphRole` via scoring
5. **Regions** → `classifier/sections.py` builds region tree via state machine
6. **Resolve** → `graph/resolver.py` creates heading/citation/TOC edges

**Output** → `output/json.py` serializes to v1 schema:
```json
{
  "docstructure_version": "v1",
  "document": {...},
  "nodes": [...],
  "edges": [...],
  "sections": [...],
  "diagnostics": [...],
  "references": [...]
}
```

**Key types already defined:**
- `ParagraphRole` enum: BODY, HEADING, TITLE, METADATA, REFERENCE, CAPTION, TOC_ENTRY, ABSTRACT, APPENDIX, AUTHOR, FOOTNOTE, ENDNOTE
- `RegionType` enum: TITLE_PAGE, ABSTRACT, TABLE_OF_CONTENTS, INTRODUCTION, METHODOLOGY, RESULTS, DISCUSSION, CONCLUSION, REFERENCES, APPENDIX, FRONT_MATTER, MAIN_CONTENT, BACK_MATTER
- `Provenance` dataclass: confidence, produced_by, version, evidence
- `BlockFeatures`: word_count, sentence_count, font_size, font_name, bold, centered, alignment, etc.

### acewriter analyzer.py — what needs cleaning

The file `acewriter/lib/document/docx/analyzer.py` (925 lines) contains:
- **Duplicate `ParagraphScores`** — defined at lines 111 and 203 (identical)
- **Dead `ParagraphScore`** — old dataclass at line 175, never referenced
- **`_v4` suffix** on 11 score functions that should be renamed (no conflict after removing old code)
- **V4 architecture** already active (BlockType, ParagraphRole with FRONT/BODY/BACK, state machine)
- Old code was already partially removed (no old ParagraphClass, CitationStyle, old detect_structure)

---

## Potential Conflicts

| Conflict | Impact | Mitigation |
|----------|--------|------------|
| Two `ParagraphScores` classes in analyzer.py | Import ambiguity if both are referenced | Remove the second (duplicate) definition — the first at line 111 is the one used by `ParagraphInfo.scores` (line 106) |
| `_v4` suffix rename breaks external callers | `stages.py`, `report_assembler.py`, `__main__.py` reference `detect_structure_v4` / `_score_*_v4` | Do rename + update all callers in a single atomic commit |
| Format detection adds latency to pipeline | Optional stage — not run unless user requests it | Keep format detection as a separate invocation, not part of the default pipeline |
| Schema v2 could break consumers of v1 output | Backward-compatible: v2 adds new top-level keys without changing existing ones | v2 remains a superset of v1. Schema validation accepts both. |

---

## Design

### 1. `formats/` — Plugin-based Format Detection

#### `formats/base.py`

```python
@dataclass
class FormatDetection:
    format_name: str          # "APA", "MLA", "IEEE"
    confidence: float         # 0.0–1.0
    signals: list[Signal]     # Individual detection signals
    evidence: list[str]       # Human-readable reasons

class FormatDetector(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def detect(self, doc: Document) -> FormatDetection:
        """Return detection result. confidence=0.0 means 'not this format'."""
```

#### `formats/__init__.py`

```python
class FormatRegistry:
    """Auto-discovers FormatDetector subclasses."""
    _detectors: dict[str, type[FormatDetector]]

    def detect_all(self, doc: Document) -> list[FormatDetection]:
        """Run ALL registered detectors, return sorted by confidence desc."""

    def detect_best(self, doc: Document) -> FormatDetection | None:
        """Return the highest-confidence detection (or None if all < threshold)."""
```

Discovery via `__init_subclass__` or explicit registration in `config.py`.

#### `formats/apa.py` — APA 7th Edition Detector

Signals checked (each weighted):

| Signal | Weight | Detection method |
|--------|--------|-----------------|
| Title page exists | 0.15 | First RegionNode is FRONT_MATTER with TITLE paragraphs |
| Running head present | 0.10 | Header text contains "Running head:" or short title |
| Abstract page | 0.15 | RegionType.ABSTRACT exists |
| References section | 0.15 | RegionType.REFERENCES exists |
| DOI in references | 0.10 | Reference text contains "doi.org/10." or "DOI:" |
| Author-date citations | 0.15 | Body text contains `(Author, YYYY)` patterns |
| Section headings (Level 1-5) | 0.10 | Heading hierarchy follows APA levels |
| Serif font (TNR 12pt) | 0.10 | `features.font_name` contains "Times" and `features.font_size` ~12 |

#### `formats/mla.py` — MLA 9th Edition Detector

| Signal | Weight | Detection method |
|--------|--------|-----------------|
| No separate title page | 0.15 | No FRONT_MATTER region with >3 non-prose blocks |
| Header: name→instructor→course→date | 0.20 | First 4 paragraphs match MLA header pattern (left-aligned, short, sequential metadata-like) |
| Works Cited section | 0.20 | RegionType.REFERENCES exists with "Works Cited" label |
| Author-page citations | 0.20 | Body text contains `(Author #)` or `(Author #- #)` patterns |
| Heading: name left-aligned | 0.10 | First line is left-aligned, not bold, has student name pattern |
| Hanging indent on citations | 0.15 | Reference paragraphs have `first_line_indent < 0` or special style |

#### `formats/ieee.py` — IEEE Detector

| Signal | Weight | Detection method |
|--------|--------|-----------------|
| Numbered references `[1]` | 0.25 | Reference paragraphs start with `[n]` pattern |
| Section order (I, II, III) | 0.20 | Headings use Roman numeral numbering |
| No author-date citations | 0.15 | Absence of `(Author, YYYY)` + presence of `[n]` in body |
| Abstract → Introduction → ... → References | 0.20 | Section sequence follows IEEE IMRAD pattern |
| Figure captions numbered | 0.10 | Captions match "Fig. n." pattern |
| Font: Times New Roman | 0.10 | Font is serif, 10pt |

### 2. `validate/rules/` — Format-Specific Validation

#### Rule structure

```python
@dataclass
class FormatRuleSet:
    """A collection of rules for a specific format."""
    format_name: str
    rules: list[Rule]

# Each Rule knows its format affinity
class Rule(ABC):
    @property
    def format(self) -> str | None:
        """Return format name if format-specific, None if generic."""
        return None

    @abstractmethod
    def check(self, doc: Document) -> list[RuleResult]: ...
```

#### APA Rules (`validate/rules/apa_rules.py`)

| Rule ID | Check | Severity |
|---------|-------|----------|
| `apa-7.01` | Running head present on title page | warning |
| `apa-7.02` | Abstract present (research papers) | info |
| `apa-7.03` | References section present | error |
| `apa-7.04` | DOI/URL in reference entries | warning |
| `apa-7.05` | Heading levels in order (1→2→3, no skipping) | warning |
| `apa-7.06` | Font is Times New Roman 12pt or equivalent | info |
| `apa-7.07` | Body starts on page 3 (after title + abstract) | warning |
| `apa-7.08` | Citations use author-date format | error |

#### MLA Rules (`validate/rules/mla_rules.py`)

| Rule ID | Check | Severity |
|---------|-------|----------|
| `mla-9.01` | No separate title page | info |
| `mla-9.02` | Header with name/instructor/course/date | warning |
| `mla-9.03` | Works Cited section present | error |
| `mla-9.04` | In-text citations use author-page format | error |
| `mla-9.05` | Hanging indent on Works Cited entries | warning |

### 3. CLI

#### `detect` subcommand

```bash
py -m docstructure detect paper.docx
# APA: 94% (title_page, abstract, doi, author_date_citations)
# MLA: 12%
# IEEE: 3%

py -m docstructure detect paper.docx --json
# {"detections": [...], "winner": "APA", "winner_confidence": 0.94}

py -m docstructure detect paper.docx --all
# Shows all detectors including low-confidence ones
```

#### Enhanced `validate`

```bash
py -m docstructure validate paper.docx
# Auto-detects format (APA), runs APA rules
# APA compliance: 67% (4/6 checks passed)
#   [PASS] apa-7.01: Running head present
#   [PASS] apa-7.02: Abstract present
#   [FAIL] apa-7.03: 2 references missing DOI
#   [PASS] apa-7.04: Heading order correct
#   [FAIL] apa-7.05: Font is 11pt (APA requires 12pt)
#   [PASS] apa-7.06: Author-date citations present

py -m docstructure validate paper.docx --format mla
# Forces MLA validation regardless of auto-detection
```

### 4. Schema Update (v2)

New top-level keys added to output (backward-compatible with v1):

```json
{
  "docstructure_version": "v2",
  "document": {...},
  "nodes": [...],
  "edges": [...],
  "sections": [...],
  "diagnostics": [...],
  "references": [...],

  "format_detection": {
    "detections": [
      {"format": "APA", "confidence": 0.94, "evidence": ["title_page", "doi_patterns"]},
      {"format": "MLA", "confidence": 0.12, "evidence": []}
    ],
    "winner": "APA",
    "winner_confidence": 0.94
  },
  "validation": {
    "format": "APA",
    "compliance_score": 0.67,
    "rule_results": [
      {"rule_id": "apa-7.01", "passed": true, "severity": "warning", "message": "..."},
      {"rule_id": "apa-7.05", "passed": false, "severity": "info", "message": "..."}
    ]
  }
}
```

---

## Related Pending Task: v4-cleanup (acewriter)

### What to do

1. **Remove duplicate `ParagraphScores`** (line 203 in `analyzer.py`) — keep only line 111 version
2. **Remove dead `ParagraphScore`** dataclass (line 175)
3. **Remove dead constants** — `COVER_KEYWORDS`, `LIST_KEYWORDS`, `TOC_KEYWORDS`, `CAPTION_PREFIXES`, `MATH_SYMBOLS`, `LIST_STYLE_KEYWORDS`, `CODE_PATTERNS`, `EQUATION_PATTERN`, `DOT_LEADERS`, `CITATION_APA`/`IEEE`/`AMA`/`MLA`/`HARVARD`, `YEAR_PATTERN`, `DOI_PATTERN`, `URL_PATTERN`
4. **Remove old helper functions** — `_find_heading`, `_section_end`, `_score_paragraph`, `_is_non_prose`, `_find_first_body_paragraph`, `_detect_cover`, `_detect_abstract`, `_detect_toc`, `_detect_lists`, `_detect_references`, `_classify_citation_style`, `_analyze_bibliography`, `_detect_appendices`, `_detect_acknowledgements`, `_detect_index`, `_detect_preface`, `_detect_glossary`, `_detect_body`, `_assemble_containers`, `_classify_paragraphs_after_regions`, `_is_in_table`, `_looks_like_code`, `_looks_like_equation`, `_looks_like_list`, old `detect_structure`
5. **Rename `_v4` suffix** — `detect_structure_v4` → `detect_structure`, `_score_body_v4` → `_score_body`, etc.
6. **Update callers** — `stages.py`, `report_assembler.py`, `__main__.py`
7. **Rewrite `compute_statistics()`** — remove `_classify_citation_style`/`_analyze_bibliography` references

### Risk — Low

V4 is already the active pipeline. This is purely subtractive cleanup.

---

## File Changes Summary

### New files (docstructure Phase 2)

```
tools/docstructure/formats/__init__.py        # FormatRegistry + auto-discovery
tools/docstructure/formats/base.py            # FormatDetector ABC, FormatDetection dataclass
tools/docstructure/formats/apa.py             # APA 7th detector (~150 lines)
tools/docstructure/formats/mla.py             # MLA 9th detector (~120 lines)
tools/docstructure/formats/ieee.py            # IEEE detector (~100 lines)
tools/docstructure/output/schema/v2.json      # Updated schema with format detection + validation blocks
tools/docstructure/validate/rules/__init__.py
tools/docstructure/validate/rules/apa_rules.py   # 8 APA compliance rules
tools/docstructure/validate/rules/mla_rules.py   # 5 MLA compliance rules
tools/docstructure/validate/rules/ieee_rules.py  # 4 IEEE compliance rules
tools/docstructure/tests/test_formats.py      # Format detection unit tests
tools/docstructure/tests/test_validation.py   # Validation rule tests
```

### Modified files

```
tools/docstructure/__main__.py                # Add detect + enhanced validate subcommands
tools/docstructure/config.py                  # Register format detectors + format rules
tools/docstructure/pipeline.py                # Add optional format detection stage
tools/docstructure/output/json.py             # Add format detection + validation to serialization
tools/docstructure/validate/base.py           # Extend Rule with format affinity, add auto-format routing
acewriter/lib/document/docx/analyzer.py       # v4-cleanup: remove dead code, rename _v4 suffix
acewriter/lib/pipeline/stages.py              # Update import after rename
acewriter/lib/document/docx/report_assembler.py  # Update import after rename
acewriter/__main__.py                         # Update import after rename
```

---

## Testing Strategy

### Format detection tests

| Test | Input | Expected |
|------|-------|----------|
| APA detection | APA-formatted paper (cover, abstract, body, references, DOI) | APA confidence > 0.7, MLA/IEEE < 0.3 |
| MLA detection | MLA-formatted paper (header, no title page, Works Cited) | MLA confidence > 0.7, APA/IEEE < 0.3 |
| IEEE detection | IEEE-formatted paper (numbered references, Roman sections) | IEEE confidence > 0.7, APA/MLA < 0.3 |
| Unknown format | Business report (no academic format signals) | All detectors < 0.3 |
| Empty document | Blank .docx | All detectors = 0.0 |

### Validation tests

| Test | Input | Expected |
|------|-------|----------|
| APA valid | Clean APA paper | All APA rules pass |
| APA invalid | APA paper with missing abstract, wrong font | Failing rules: apa-7.02, apa-7.06 |
| MLA valid | Clean MLA paper | All MLA rules pass |
| Auto-format | APA paper validated without --format | Auto-detects APA, runs APA rules |

### Golden tests

- Add format detection + validation results to existing golden files
- Regenerate golden data after changes

### v4-cleanup regression tests

```bash
py -m acewriter structure sample.docx           # verify regions unchanged
py -m acewriter structure sample.docx --debug   # verify debug output format
python3 -c "from acewriter.lib.document.docx.analyzer import detect_structure"  # no import errors
```

---

## Execution Log

### 2026-07-04 — Phase 2a: format detection plugins
- [x] Created `formats/base.py` — FormatDetector ABC, FormatDetection dataclass, Signal dataclass
- [x] Created `formats/__init__.py` — FormatRegistry with `__init_subclass__` auto-discovery
- [x] Created `formats/apa.py` — 8-signal APA 7th detector
- [x] Created `formats/mla.py` — 6-signal MLA 9th detector
- [x] Created `formats/ieee.py` — 6-signal IEEE detector
- [x] Created `output/schema/v2.json` — v2 schema with `format_detection` + `validation`
- [x] Updated `output/json.py` — emit v2 schema, format detection + validation blocks
- [x] Updated `config.py` — register format detectors
- [x] Updated `__main__.py` — add `detect` CLI subcommand
- [x] Updated `pipeline.py` — add optional format detection stage
- [x] Updated `validate/base.py` — format affinity + auto-format routing
- [x] Created `tests/test_formats.py` — 8 unit tests

### 2026-07-04 — Phase 2b: format-specific validation rules
- [x] Created `validate/rules/__init__.py` — rule registry
- [x] Created `validate/rules/apa_rules.py` — 7 APA rules
- [x] Created `validate/rules/mla_rules.py` — 5 MLA rules
- [x] Created `validate/rules/ieee_rules.py` — 4 IEEE rules
- [x] Enhanced `validate` CLI with `--format` flag
- [x] Created `tests/test_validation.py` — 10 unit tests

### 2026-07-04 — Phase 2c: v4-cleanup (acewriter analyzer)
- [x] Removed dead `ParagraphScore` dataclass (line 175)
- [x] Removed duplicate `ParagraphScores` class (line 203)
- [x] Renamed `_v4` suffix on all 11 score functions
- [x] Renamed `detect_structure_v4` → `detect_structure`
- [x] Updated all callers: `stages.py`, `report_assembler.py`, `__main__.py`
- [x] Removed all old helper functions and dead constants
- [x] Replaced `compute_statistics()` — removed dead references

### 2026-07-04 — Verification
- [x] Golden tests pass (5/5, regenerated for v2 schema)
- [x] Stress tests pass (16/16, 2 expected skips)
- [x] Format detection tests pass (8/8)
- [x] Validation rule tests pass (10/10)
- [x] `py -m acewriter structure .samples/sample.docx` works
- [x] `from acewriter.lib.document.docx.analyzer import detect_structure, ParagraphScores` works
- [x] No remaining `_v4` or old `ParagraphScore` references

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Format detectors too sensitive (false positives) | Medium | Medium | Set threshold at 0.3; show all detectors; let user override |
| Format detectors too strict (false negatives) | Medium | Low | Threshold at 0.3 still catches strong signals; --all flag shows everything |
| v4-cleanup breaks acewriter | Low | High | Test all 3 commands (structure, score, humanize) before committing |
| Schema v2 breaks existing consumers | Low | Low | Only adds new keys; existing consumers that ignore unknown fields are fine |
| Duplicate ParagraphScores removal breaks import | Low | Medium | Check all imports of `ParagraphScores` in acewriter before removing |

---

## Backward Compatibility

- **Schema v2 is a superset of v1** — all v1 keys unchanged, new keys added alongside
- **Format detection is opt-in** — not run by default in the pipeline; user must invoke `detect` or `validate`
- **v4-cleanup is purely subtractive** — removes dead code, renames `_v4` suffix. All external behavior preserved (same regions, same classifications)
- **CLI changes are additive** — `detect` is new; `validate` gains `--format` flag (defaults to `auto`)

---

## Migration/Rollout Strategy

1. **Phase 2a — formats/ plugin system + APA/MLA/IEEE detectors**
   - Build `formats/base.py`, `formats/__init__.py` with registry
   - Implement APA, MLA, IEEE detectors
   - Add `detect` CLI subcommand
   - Add format detection to JSON output (schema v2)
   - Tests: golden + unit

2. **Phase 2b — Format-specific validation rules**
   - Extend `validate/base.py` with format affinity
   - Implement APA/MLA/IEEE rule sets
   - Enhance `validate` CLI with `--format` flag
   - Add validation to JSON output

3. **Phase 2c — v4-cleanup (acewriter analyzer)**
   - Remove dead code from analyzer.py
   - Rename _v4 suffix
   - Update all callers
   - Regression test acewriter

**Rollback plan:** Each phase is independently reversible. If format detection has issues, revert only `formats/` directory. If v4-cleanup breaks acewriter, revert the single commit on analyzer.py.

---

## Success Criteria

```bash
# 1. Format detection works
py -m docstructure detect .samples/sample.docx
# → APA: 94%, MLA: 12%, IEEE: 3%

# 2. JSON output includes format detection
py -m docstructure detect .samples/sample.docx --json | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert 'format_detection' in d
assert 'detections' in d['format_detection']
assert 'winner' in d['format_detection']
"

# 3. Validation with auto-format detection
py -m docstructure validate .samples/sample.docx
# → APA compliance: X/X checks passed

# 4. Explicit format validation
py -m docstructure validate .samples/sample.docx --format apa
# → APA compliance: X/X checks passed

# 5. v4-cleanup — acewriter still works
py -m acewriter structure .samples/sample.docx
# → FRONT 0-7, BODY 8-22, BACK 23-28

# 6. No duplicate classes in analyzer.py
python3 -c "
from acewriter.lib.document.docx.analyzer import ParagraphScores, detect_structure
assert ParagraphScores is not None
"
```
