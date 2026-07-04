"""Benchmark runner — measures docstructure pipeline performance.

Records per-document:
  - wall time (per stage and total)
  - CPU time (per stage and total)
  - peak RSS memory
  - JSON output size
  - node count
  - edge count

Results saved to benchmarks/results/ as JSON for diffing across versions.

Usage:
    python benchmarks/run.py              # full suite
    python benchmarks/run.py --quick      # XS, S, M only
    python benchmarks/run.py --compare    # diff against previous results
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

_script_dir = os.path.dirname(os.path.abspath(__file__))
# docstructure package is at tools/docstructure/; add tools/ to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(_script_dir)))

from docstructure.pipeline import run_pipeline
from docstructure.output.json import serialize

BENCHMARK_DIR = Path(__file__).parent
DOCS_DIR = BENCHMARK_DIR / "docs"
RESULTS_DIR = BENCHMARK_DIR / "results"
STRESS_DIR = Path(__file__).parent.parent.parent / ".samples" / "stress"

BENCHMARKS = {
    "XS":   {"size": 10,  "label": "10 paragraphs"},
    "S":    {"size": 100, "label": "100 paragraphs"},
    "M":    {"size": 500, "label": "500 paragraphs"},
    "L":    {"size": 1000, "label": "1000 paragraphs"},
    "XL":   {"size": 2500, "label": "2500 paragraphs"},
    "XXL":  {"size": 5000, "label": "5000 paragraphs"},
}

QUICK_BENCHMARKS = ["XS", "S", "M"]


def _get_doc_path(size: int) -> Path:
    """Get the path for a synthetic benchmark doc; generate if missing."""
    path = DOCS_DIR / f"bench_{size}para.docx"
    if not path.exists():
        from benchmarks.generate import generate_docx
        print(f"  Generating benchmark document ({size} paragraphs)...")
        generate_docx(size, path)
    return path


def _measure_peak_rss() -> int:
    """Return peak RSS in bytes."""
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return usage.ru_maxrss * 1024  # Linux: ru_maxrss is in KB
    except AttributeError:
        return 0


def _run_benchmark(size: int, label: str) -> dict:
    """Run pipeline and collect all metrics."""
    doc_path = _get_doc_path(size)
    doc_path_str = str(doc_path)

    tracemalloc.start()
    start_wall = time.perf_counter()
    start_cpu = time.process_time()

    stages = {}

    # Parse
    t0 = time.perf_counter()
    from docstructure.parser.docx import DOCXParser
    parser = DOCXParser()
    doc = parser.parse(doc_path_str)
    t1 = time.perf_counter()
    stages["parse"] = {"wall": t1 - t0}

    # Normalize
    from docstructure.normalizer.normalize import normalize
    t0 = time.perf_counter()
    normalize(doc)
    t1 = time.perf_counter()
    stages["normalize"] = {"wall": t1 - t0}

    # Features
    from docstructure.features import extract_features
    t0 = time.perf_counter()
    extract_features(doc)
    t1 = time.perf_counter()
    stages["features"] = {"wall": t1 - t0}

    # Classify
    from docstructure.classifier.paragraph import classify_paragraphs
    t0 = time.perf_counter()
    classify_paragraphs(doc)
    t1 = time.perf_counter()
    stages["classify"] = {"wall": t1 - t0}

    # Regions
    from docstructure.classifier.sections import build_regions
    t0 = time.perf_counter()
    build_regions(doc)
    t1 = time.perf_counter()
    stages["regions"] = {"wall": t1 - t0}

    # Resolve
    from docstructure.graph.resolver import resolve_relationships
    t0 = time.perf_counter()
    resolve_relationships(doc)
    t1 = time.perf_counter()
    stages["resolve"] = {"wall": t1 - t0}

    end_cpu = time.process_time()
    end_wall = time.perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_rss = _measure_peak_rss()

    json_data = serialize(doc)
    json_size = len(json.dumps(json_data))

    return {
        "label": label,
        "size": size,
        "actual_paragraphs": len(doc.paragraphs),
        "node_count": len(doc.nodes),
        "edge_count": len(doc.edges),
        "json_size_bytes": json_size,
        "total_wall_seconds": end_wall - start_wall,
        "total_cpu_seconds": end_cpu - start_cpu,
        "peak_rss_bytes": peak_rss,
        "peak_traced_memory_bytes": peak,
        "stages": stages,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_benchmarks(keys: list[str]) -> list[dict]:
    results = []
    for key in keys:
        info = BENCHMARKS[key]
        print(f"  [{key}] {info['label']}...")
        result = _run_benchmark(info["size"], info["label"])
        results.append(result)
        wall = result["total_wall_seconds"]
        cpu = result["total_cpu_seconds"]
        nodes = result["node_count"]
        json_kb = result["json_size_bytes"] / 1024
        rss_mb = result["peak_rss_bytes"] / (1024 * 1024)
        print(f"    nodes={nodes} wall={wall:.2f}s cpu={cpu:.2f}s json={json_kb:.0f}KB rss={rss_mb:.0f}MB")
    return results


def print_summary(results: list[dict]) -> None:
    print()
    print(f"{'Label':<12} {'Nodes':>7} {'Edges':>6} {'Wall(s)':>9} {'CPU(s)':>8} {'JSON':>8} {'RSS':>8}")
    print("-" * 65)
    for r in results:
        wall_s = f"{r['total_wall_seconds']:.2f}"
        cpu_s = f"{r['total_cpu_seconds']:.2f}"
        json_s = f"{r['json_size_bytes']/1024:.0f}KB"
        rss_s = f"{r['peak_rss_bytes']/(1024*1024):.0f}MB"
        print(f"{r['label']:<12} {r['node_count']:>7} {r['edge_count']:>6} {wall_s:>9} {cpu_s:>8} {json_s:>8} {rss_s:>8}")
    print()


def save_results(results: list[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"bench_{timestamp}.json"
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Results saved: {path}")
    return path


def compare_results(new_path: Path) -> None:
    """Compare new results against the previous run."""
    existing = sorted(RESULTS_DIR.glob("bench_*.json"))
    if len(existing) < 2:
        print("  Need at least 2 result files to compare")
        return
    # Find the second-to-last (the one before this new run)
    prev_path = existing[-2] if len(existing) >= 2 else existing[0]
    if prev_path == new_path and len(existing) >= 2:
        prev_path = existing[-2]

    with open(prev_path) as f:
        prev = json.load(f)
    with open(new_path) as f:
        curr = json.load(f)

    print()
    print("  Comparison with previous run:")
    print(f"  Previous: {prev_path.name}")
    print(f"  Current:  {new_path.name}")
    print()

    prev_map = {r["label"]: r for r in prev}
    curr_map = {r["label"]: r for r in curr}

    for label in prev_map:
        if label not in curr_map:
            continue
        p = prev_map[label]
        c = curr_map[label]
        wall_delta = c["total_wall_seconds"] - p["total_wall_seconds"]
        rss_delta = c["peak_rss_bytes"] - p["peak_rss_bytes"]
        wall_pct = (wall_delta / p["total_wall_seconds"] * 100) if p["total_wall_seconds"] else 0
        rss_pct = (rss_delta / p["peak_rss_bytes"] * 100) if p["peak_rss_bytes"] else 0
        print(f"  {label:<10} wall: {wall_delta:+.2f}s ({wall_pct:+.0f}%)  rss: {rss_delta/(1024*1024):+.0f}MB ({rss_pct:+.0f}%)")


def main():
    parser = argparse.ArgumentParser(description="DocStructure benchmark runner")
    parser.add_argument("--quick", action="store_true", help="Run XS, S, M only")
    parser.add_argument("--compare", action="store_true", help="Compare with previous results")
    args = parser.parse_args()

    print("=" * 60)
    print("  DocStructure Benchmark Suite")
    print("=" * 60)
    print()

    keys = list(QUICK_BENCHMARKS) if args.quick else list(BENCHMARKS.keys())

    results = run_benchmarks(keys)

    if results:
        print_summary(results)
        new_path = save_results(results)

    if args.compare and results:
        compare_results(new_path)


if __name__ == "__main__":
    main()
