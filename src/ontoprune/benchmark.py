"""
OntoPrune Benchmark CLI Entrypoint.
Conforms to ontoprune.md Section 7 command and supports live inference benchmarking:
python -m ontoprune.benchmark --file fixtures/sample_service.py --func procesar_orden --backend gemini
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add benchmark and project root to path
root_dir = Path(__file__).resolve().parent.parent.parent
bench_dir = root_dir / "benchmark"
if str(bench_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from benchmark.runner import execute_benchmark, format_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ontoprune.benchmark",
        description="OntoPrune Benchmark Runner (Naive vs OntoPrune Empirical Evaluation)",
    )
    parser.add_argument("--file", required=True, type=str, help="Target Python source file")
    parser.add_argument("--func", required=True, type=str, help="Target function or method name")
    parser.add_argument(
        "--backend",
        default="gemini",
        choices=["gemini", "ollama"],
        help="Inference engine backend (default: gemini)",
    )
    parser.add_argument(
        "--model",
        default=None,
        type=str,
        help="LLM model identifier (defaults: gemini-2.5-flash for gemini, qwen2.5-coder:3b for ollama)",
    )
    parser.add_argument(
        "--host", default="http://localhost:11434", type=str, help="Ollama host URL"
    )
    parser.add_argument(
        "--format",
        "-f",
        default="stubs",
        choices=["stubs", "turtle", "json", "nl"],
        help="Context format for OntoPrune (default: stubs)",
    )
    parser.add_argument(
        "--task",
        default="refactor",
        choices=["refactor", "unit_test"],
        help="Evaluation task prompt (default: refactor)",
    )
    parser.add_argument("--runs", default=3, type=int, help="Number of benchmark runs (default: 3)")
    parser.add_argument(
        "--compare-formats",
        action="store_true",
        help="Execute format ablation comparing stubs, turtle, json, and nl",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run token and CPU benchmarks without contacting inference API",
    )

    args = parser.parse_args(argv)

    try:
        results = execute_benchmark(
            file_path=args.file,
            target_func=args.func,
            backend=args.backend,
            model=args.model,
            host=args.host,
            fmt=args.format,
            task=args.task,
            runs=args.runs,
            compare_formats=args.compare_formats,
            dry_run=args.dry_run,
        )
        report_str = format_report(results)
        sys.stdout.write(report_str + "\n")
        return 0
    except Exception as err:
        sys.stderr.write(f"Benchmark error: {err}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
