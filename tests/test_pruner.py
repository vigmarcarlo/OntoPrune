"""
Unit and performance tests for ontoprune.pruner.
"""

import time
from pathlib import Path

from rdflib import RDF, Namespace

from ontoprune.parser import parse_file
from ontoprune.pruner import prune_subgraph

SOFT = Namespace("https://w3id.org/ontoprune/software#")
REPO = Namespace("https://w3id.org/ontoprune/repo/")


def test_prune_procesar_orden() -> None:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_service.py"
    graph = parse_file(fixture_path)

    subgraph, target_uri = prune_subgraph(graph, "OrderService.procesar_orden")

    assert target_uri == REPO["func_OrderService.procesar_orden"]
    assert (target_uri, RDF.type, SOFT.Function) in subgraph

    # Verify directly invoked methods are present
    invoked = set(subgraph.objects(target_uri, SOFT.invokes))
    assert len(invoked) > 0

    assert REPO["func_OrderService.validar_orden"] in invoked
    assert REPO["func_InventoryService.reservar_stock"] in invoked
    assert REPO["func_PaymentGateway.cobrar"] in invoked
    assert REPO["func_BillingService.emitir_factura"] in invoked
    assert REPO["func_OrderRepository.update_status"] in invoked

    # Verify unrelated methods are NOT present in subgraph
    assert REPO["func_OrderRepository.find_by_customer"] not in subgraph.subjects()
    assert REPO["func_PaymentGateway.reembolsar"] not in subgraph.subjects()
    assert REPO["func_BaseService.generate_token"] not in subgraph.subjects()


def test_pruning_determinism_5_runs() -> None:
    """Verify criterion: 5 consecutive runs produce 0 variance in serialized output."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_service.py"

    serialized_results = []
    for _ in range(5):
        graph = parse_file(fixture_path)
        subgraph, target_uri = prune_subgraph(graph, "procesar_orden")
        serialized_results.append(subgraph.serialize(format="turtle"))

    for i in range(1, 5):
        assert serialized_results[i] == serialized_results[0], f"Run {i} differed from run 0"


def test_pruning_cpu_overhead_under_15ms() -> None:
    """Verify performance criterion: combined AST parse + SPARQL query <= 15 ms in warm runs."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_service.py"

    # Warmup
    g_warm = parse_file(fixture_path)
    prune_subgraph(g_warm, "procesar_orden")

    # Measure 10 runs
    times_ms = []
    for _ in range(10):
        t0 = time.perf_counter()
        g = parse_file(fixture_path)
        prune_subgraph(g, "procesar_orden")
        t_elapsed = (time.perf_counter() - t0) * 1000.0
        times_ms.append(t_elapsed)

    median_ms = sorted(times_ms)[len(times_ms) // 2]
    # Expect median time <= 15.0 ms
    assert median_ms <= 15.0, f"Overhead {median_ms:.2f} ms exceeded budget of 15.0 ms"
