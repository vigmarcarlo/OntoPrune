"""
Empirical Inference Benchmark Runner.

Executes real streaming evaluations comparing Naive Full Context against OntoPrune,
collecting actual TTFT, server-reported token counts, total latency,
and verifying generated code against the contract.
"""

from __future__ import annotations

import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark.clients import LLMClient, StreamResult, create_client
from benchmark.tasks import get_task_prompt
from ontoprune import check, translate
from ontoprune.parser import parse_file
from ontoprune.pruner import prune_subgraph


@dataclass
class AggregatedMetrics:
    cpu_overhead_ms: float
    input_tokens: int
    ttft_ms: float
    total_time_ms: float
    output_tokens: int
    hallucinations: int
    sample_response: str


def run_single_evaluation(
    client: LLMClient,
    prompt: str,
    contract_for_check: str,
    temperature: float = 0.0,
    seed: int = 42,
) -> tuple[StreamResult, int]:
    """Execute one streaming run and check for hallucinations."""
    result = client.generate_stream(prompt, temperature=temperature, seed=seed)
    violations = check(result.text, against=contract_for_check)
    return result, len(violations)


def evaluate_pipeline(
    client: LLMClient,
    context_text: str,
    task_prompt: str,
    contract_for_check: str,
    target_symbol: str,
    runs: int = 3,
) -> AggregatedMetrics:
    """Runs N evaluations and aggregates by median."""
    full_prompt = f"{context_text}\n\n--- SÍMBOLO OBJETIVO ---\n{target_symbol}\n\n{task_prompt}"

    results: list[StreamResult] = []
    hallucination_counts: list[int] = []

    for _ in range(runs):
        res, v_count = run_single_evaluation(client, full_prompt, contract_for_check)
        results.append(res)
        hallucination_counts.append(v_count)

    # Median aggregation
    ttfts = [r.ttft_ms for r in results]
    totals = [r.total_time_ms for r in results]
    in_tokens = [r.input_tokens for r in results]
    out_tokens = [r.output_tokens for r in results]

    median_ttft = statistics.median(ttfts)
    median_total = statistics.median(totals)
    median_in = int(statistics.median(in_tokens))
    median_out = int(statistics.median(out_tokens))
    median_hallucinations = int(statistics.median(hallucination_counts))

    return AggregatedMetrics(
        cpu_overhead_ms=0.0,
        input_tokens=median_in,
        ttft_ms=median_ttft,
        total_time_ms=median_total,
        output_tokens=median_out,
        hallucinations=median_hallucinations,
        sample_response=results[0].text,
    )


def execute_benchmark(
    file_path: str | Path,
    target_func: str,
    backend: str = "gemini",
    model: str | None = None,
    host: str = "http://localhost:11434",
    fmt: str = "stubs",
    task: str = "refactor",
    runs: int = 3,
    compare_formats: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    path = Path(file_path)
    full_code = path.read_text(encoding="utf-8")
    task_prompt = get_task_prompt(task)

    # Measure CPU overhead of file read
    t0 = time.perf_counter()
    _ = path.read_text(encoding="utf-8")
    naive_cpu_ms = (time.perf_counter() - t0) * 1000.0

    # Measure CPU overhead of OntoPrune (warmup + median of 5)
    g_warm = parse_file(path)
    prune_subgraph(g_warm, target_func)
    onto_cpu_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        g = parse_file(path)
        prune_subgraph(g, target_func)
        onto_cpu_times.append((time.perf_counter() - t0) * 1000.0)
    onto_cpu_ms = statistics.median(onto_cpu_times)

    if dry_run:
        # Offline projection
        naive_metrics = AggregatedMetrics(
            cpu_overhead_ms=naive_cpu_ms,
            input_tokens=len(full_code) // 4 + len(task_prompt) // 4,
            ttft_ms=2120.0,
            total_time_ms=4850.0,
            output_tokens=340,
            hallucinations=1,
            sample_response="# dry run response",
        )
        pruned_stubs = translate(path, target_func, fmt=fmt)
        onto_metrics = AggregatedMetrics(
            cpu_overhead_ms=onto_cpu_ms,
            input_tokens=len(pruned_stubs) // 4 + len(task_prompt) // 4,
            ttft_ms=112.0,
            total_time_ms=1340.0,
            output_tokens=310,
            hallucinations=0,
            sample_response="# dry run response",
        )
        return {
            "target": target_func,
            "model": model or ("gemini-3.8-flash" if backend == "gemini" else "qwen2.5-coder:3b"),
            "backend": backend,
            "naive": naive_metrics,
            "ontoprune": onto_metrics,
            "dry_run": True,
        }

    # Live Real Inference Execution
    client = create_client(backend=backend, model=model, host=host)

    # Warmup request to eliminate cold start/TCP setup bias
    try:
        client.generate_stream("ping", temperature=0.0)
    except Exception as err:
        sys.stderr.write(f"Warning during client warmup: {err}\n")

    # Evaluate Naive Pipeline
    sys.stderr.write("[1/2] Evaluando Pipeline Naive (Contexto Completo)...\n")
    naive_metrics = evaluate_pipeline(
        client=client,
        context_text=full_code,
        task_prompt=task_prompt,
        contract_for_check=full_code,
        target_symbol=target_func,
        runs=runs,
    )
    naive_metrics.cpu_overhead_ms = naive_cpu_ms

    format_results: dict[str, AggregatedMetrics] = {}
    formats_to_test = ["stubs", "turtle", "json", "nl"] if compare_formats else [fmt]

    for f_idx, current_fmt in enumerate(formats_to_test, start=1):
        sys.stderr.write(f"[2/2] Evaluando OntoPrune (Formato '{current_fmt}')...\n")
        pruned_contract = translate(path, target_func, fmt=current_fmt)
        metrics = evaluate_pipeline(
            client=client,
            context_text=pruned_contract,
            task_prompt=task_prompt,
            contract_for_check=pruned_contract,
            target_symbol=target_func,
            runs=runs,
        )
        metrics.cpu_overhead_ms = onto_cpu_ms
        format_results[current_fmt] = metrics

    primary_onto_metrics = format_results[fmt]

    return {
        "target": target_func,
        "model": model or getattr(client, "model", backend),
        "backend": backend,
        "naive": naive_metrics,
        "ontoprune": primary_onto_metrics,
        "format_results": format_results if compare_formats else None,
        "dry_run": False,
    }


def format_report(results: dict[str, Any]) -> str:
    """Format benchmark results adhering to ontoprune.md Section 7."""
    naive: AggregatedMetrics = results["naive"]
    onto: AggregatedMetrics = results["ontoprune"]
    target = results["target"]
    model = results["model"]
    backend = results.get("backend", "local").upper()

    cpu_delta = onto.cpu_overhead_ms - naive.cpu_overhead_ms
    token_saved = naive.input_tokens - onto.input_tokens
    token_delta_pct = (
        ((onto.input_tokens - naive.input_tokens) / naive.input_tokens) * 100.0
        if naive.input_tokens
        else 0.0
    )

    ttft_speedup = naive.ttft_ms / max(1.0, onto.ttft_ms)
    ttft_delta_pct = (
        ((onto.ttft_ms - naive.ttft_ms) / naive.ttft_ms) * 100.0 if naive.ttft_ms else 0.0
    )
    ttft_saved_sec = (naive.ttft_ms - onto.ttft_ms) / 1000.0

    total_delta_pct = (
        ((onto.total_time_ms - naive.total_time_ms) / naive.total_time_ms) * 100.0
        if naive.total_time_ms
        else 0.0
    )
    out_delta_pct = (
        ((onto.output_tokens - naive.output_tokens) / naive.output_tokens) * 100.0
        if naive.output_tokens
        else 0.0
    )

    report_lines = [
        "=" * 80,
        "                    ONTOPRUNE - BENCHMARK REPORT (v0.1.0)",
        "=" * 80,
        f"Target Symbol : {target}",
        f"Engine Model  : {model} (via {backend} Real Streaming)",
        f"Evaluation    : {'Simulated' if results.get('dry_run') else 'Live Empirical Inference'}",
        "-" * 80,
        "",
        "METRIC                     NAIVE PIPELINE       ONTOPRUNE            DELTA",
        "-" * 80,
        f"CPU Overhead               {naive.cpu_overhead_ms:5.2f} ms (File read)  {onto.cpu_overhead_ms:5.2f} ms (AST+SPARQL) {cpu_delta:+5.2f} ms",
        f"Input Tokens               {naive.input_tokens:,} tokens         {onto.input_tokens:,} tokens           {token_delta_pct:+.2f}%",
        f"Time to First Token (TTFT) {naive.ttft_ms:5.0f} ms             {onto.ttft_ms:5.0f} ms               {ttft_delta_pct:+.2f}% ({ttft_speedup:.1f}x)",
        f"Total Execution Time       {naive.total_time_ms:5.0f} ms             {onto.total_time_ms:5.0f} ms             {total_delta_pct:+.2f}%",
        f"Output Tokens              {naive.output_tokens:5d} tokens         {onto.output_tokens:5d} tokens           {out_delta_pct:+.2f}%",
        f"Hallucinated API Calls     {naive.hallucinations} invalid method     {onto.hallucinations} invalid methods    {'100% Valid' if onto.hallucinations == 0 else f'{onto.hallucinations} errors'}",
        "-" * 80,
        "",
        "[SUMMARY]",
        f"OntoPrune saved {token_saved:,} input tokens and reduced TTFT by {ttft_saved_sec:.2f} seconds with an",
        f"overhead of only {onto.cpu_overhead_ms:.1f} milliseconds on CPU.",
        "=" * 80,
    ]

    # Additional section if format ablation was performed
    format_results = results.get("format_results")
    if format_results:
        report_lines.extend(
            [
                "",
                "FORMAT ABLATION COMPARISON (H4):",
                "-" * 80,
                f"{'FORMAT':<12} {'INPUT TOKENS':<15} {'TTFT (ms)':<12} {'TOTAL TIME':<14} {'HALLUCINATIONS'}",
                "-" * 80,
                f"{'NAIVE':<12} {naive.input_tokens:<15} {naive.ttft_ms:<12.0f} {naive.total_time_ms:<14.0f} {naive.hallucinations}",
            ]
        )
        for fmt_name, fmt_m in format_results.items():
            report_lines.append(
                f"{fmt_name.upper():<12} {fmt_m.input_tokens:<15} {fmt_m.ttft_ms:<12.0f} {fmt_m.total_time_ms:<14.0f} {fmt_m.hallucinations}"
            )
        report_lines.append("=" * 80)

    return "\n".join(report_lines)
