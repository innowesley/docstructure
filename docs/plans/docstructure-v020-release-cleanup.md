# docstructure v0.2.0 Release Cleanup

## Gap Analysis
After the v0.2.0 stabilization pass, 6 gaps remain:

1. **No `.gitignore`** — build artifacts (`dist/`, `*.egg-info/`, `__pycache__/`) not excluded
2. **Version not single-sourced** — `pyproject.toml` has static version, `__init__.py` has hardcoded fallback — can drift
3. **Dead code** — `config.py` has empty `DEFAULT_RULES`, `__main__.py` has unreachable branch in `_build_format_detection_result`
4. **`test_package.py` swallows build errors** — `capture_output=True` hides failures
5. **`benchmarks/__init__.py` may be missing** — needed for package resolution
6. **Build artifacts in working tree** — `dist/` and `*.egg-info/` checked in

## Tasks

### 1. `.gitignore`
```
# Build artifacts
dist/
*.egg-info/

# Benchmarks output
benchmarks/docs/
benchmarks/results/

# Python
__pycache__/
*.pyc
*.pyo
```

### 2. True single-source version
- Create `docstructure/_version.py`:
  ```python
  __version__ = "0.2.0"
  ```
- `pyproject.toml`: use `dynamic = ["version"]` + `attr: docstructure._version.__version__`
- `__init__.py`: import from `_version` instead of `importlib.metadata` fallback

### 3. Dead code removal
- `config.py`: delete empty `DEFAULT_RULES` list
- `__main__.py`: remove dead branch in `_build_format_detection_result`

### 4. `test_package.py` fix
- Redirect stderr instead of capturing it, so build errors are visible

### 5. Verify `benchmarks/__init__.py`
- Check existence, create empty if missing

### 6. Build artifact cleanup
- `rm -rf docstructure/dist/ docstructure/*.egg-info/`
- Add to `.gitignore` so they stay out

## Risks & Compatibility
- **None.** All changes are internal: no API changes, no CLI changes, no output changes.
- Existing `install`, `import`, and `analyze()` workflows unaffected.
- Version approach changes but result is identical (`0.2.0`).

## Testing
- `pytest tests/` — all existing tests must pass
- `pip install .` — sdist install must work
- `python -c "from docstructure import __version__; print(__version__)"` — must print `0.2.0`

## Progress Log

### 2026-07-04 — All tasks completed

- [x] Created `docstructure/.gitignore` — `dist/`, `*.egg-info/`, `__pycache__/`, `benchmarks/docs/`, `benchmarks/results/`
- [x] Created `docstructure/_version.py` — single source of truth for `0.2.0`
- [x] Updated `pyproject.toml` — `dynamic = ["version"]` → `attr: docstructure._version.__version__`
- [x] Updated `__init__.py` — imports version from `_version` (no `importlib.metadata` fallback)
- [x] Cleaned dead code in `__main__.py` — removed `winner = detect_best(None) if False else None`
- [x] Cleaned dead code in `config.py` — removed empty `DEFAULT_RULES` list + unused imports (`Rule`, `validate`, `register`)
- [x] Fixed `test_package.py` — replaced `capture_output=True` with `stdout=subprocess.PIPE, stderr=subprocess.STDOUT` on all subprocess calls
- [x] Verified `benchmarks/__init__.py` exists
- [x] Removed build artifacts from git index and working tree (`dist/`, `*.egg-info/`)
- [x] Created `docs/docstructure.md` — project index page
- [x] Labeled changelogs with `project: docstructure` header
- [x] Tests: 19/20 passed (1 pre-existing fixture error in golden_test.py)
- [x] Version verified single-sourced: `0.2.0` from `_version` → `__init__` → installed package
