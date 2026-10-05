"""
Unit test for benchmark execution and report formatting.
"""

from pathlib import Path

from benchmark.runner import execute_benchmark, format_report


def test_benchmark_dry_run_execution() -> None:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_service.py"
    results = execute_benchmark(
        file_path=fixture_path,
        target_func="procesar_orden",
        model="qwen2.5-coder:3b",
        dry_run=True,
    )

    assert results["target"] == "procesar_orden"
    assert results["naive"].input_tokens > results["ontoprune"].input_tokens

    # Verify report formatting works without errors
    report = format_report(results)
    assert "ONTOPRUNE - BENCHMARK REPORT" in report
    assert "Input Tokens" in report
    assert "CPU Overhead" in report
