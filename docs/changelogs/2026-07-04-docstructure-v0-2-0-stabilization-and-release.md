project: docstructure
<!-- GENERATED FILE -- DO NOT EDIT -->
<!-- generator: doc-it changelog-generator -->
<!-- source: changelog-generator.ts -->
<!-- generated-at: 2026-07-04T00:45:05.399Z -->

# 2026-07-04 — docstructure v0.2.0 — Stabilization and Release

- Packaging: pyproject.toml (modern setuptools, setuptools.build_meta), setup.py, LICENSE (MIT), pip-installable
- Public API freeze: __all__ exports analyze, parse, detect_format, validate, serialize, to_json, to_file, __version__
- Schema stability: v2 as default, --schema v1|v2 flag, v1 frozen as deprecated
- CLI: --version flag, --schema flag on analyze, centralized error handling with exit codes
- Error handling: typed exception hierarchy (DocStructureError → ParseError / UnsupportedFormatError), hardening in parser and pipeline
- Benchmarks: synthetic document generator (deterministic, varied structure), benchmark runner (wall/CPU time, peak RSS, JSON size, node/edge counts)
- Documentation: full README.md (quick start, CLI, API, architecture, schema, validation, formats, development)
- Packaging compatibility test: builds sdist, installs in fresh venv, smoke-tests

**Affected features:** docstructure
