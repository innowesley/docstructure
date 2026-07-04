project: docstructure
<!-- GENERATED FILE -- DO NOT EDIT -->
<!-- generator: doc-it changelog-generator -->
<!-- source: changelog-generator.ts -->
<!-- generated-at: 2026-07-04T00:22:39.574Z -->

# 2026-07-04 — Phase 2: Format Detection + Validation + acewriter Cleanup

- Created `formats/` plugin system: FormatDetector ABC, FormatRegistry with auto-discovery
- Implemented APA 7th, MLA 9th, and IEEE format detectors (18 signals total)
- Created format-specific validation rules: 7 APA, 5 MLA, 4 IEEE rules
- Added `detect` CLI subcommand + enhanced `validate` with `--format` flag
- Updated JSON output to v2 schema with `format_detection` and `validation` blocks
- Cleaned `acewriter/lib/document/docx/analyzer.py`: removed dead ParagraphScore, duplicate ParagraphScores, all old helper functions and constants; renamed `_v4` suffix; updated all callers
- Added 18 new unit tests; regenerated golden files for v2 schema

**Affected features:** docstructure, acewriter
