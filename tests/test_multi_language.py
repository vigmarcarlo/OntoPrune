"""
Unit and Integration Tests for Multi-Language Support (Dart, Java, TypeScript).
"""

from pathlib import Path

from rdflib import RDF, RDFS, Namespace

import ontoprune
from ontoprune.pruner import prune_subgraph

SOFT = Namespace("https://w3id.org/ontoprune/software#")


def test_dart_parser_structure() -> None:
    """Verify Dart parser extracts classes, methods, return types, and invocations."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_flutter_service.dart"
    graph = ontoprune.parse_file(fixture_path)

    # Verify classes
    classes = {
        str(o)
        for s, p, o in graph.triples((None, RDFS.label, None))
        if (s, RDF.type, SOFT.Class) in graph
    }
    assert "InventoryService" in classes
    assert "BillingService" in classes
    assert "OrderService" in classes

    # Verify target function and invocation
    subgraph, target_uri = prune_subgraph(graph, "procesarOrden")
    assert target_uri is not None
    invoked = list(subgraph.objects(target_uri, SOFT.invokes))
    assert len(invoked) >= 2  # reservarStock, emitirFactura


def test_java_parser_structure() -> None:
    """Verify Java parser extracts classes, methods, types, and invocations."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "SampleJavaService.java"
    graph = ontoprune.parse_file(fixture_path)

    classes = {
        str(o)
        for s, p, o in graph.triples((None, RDFS.label, None))
        if (s, RDF.type, SOFT.Class) in graph
    }
    assert "InventoryService" in classes
    assert "BillingService" in classes
    assert "OrderService" in classes

    subgraph, target_uri = prune_subgraph(graph, "procesarOrden")
    assert target_uri is not None
    invoked = list(subgraph.objects(target_uri, SOFT.invokes))
    assert len(invoked) >= 2


def test_typescript_parser_structure() -> None:
    """Verify TypeScript parser extracts classes, methods, types, and invocations."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_ts_service.ts"
    graph = ontoprune.parse_file(fixture_path)

    classes = {
        str(o)
        for s, p, o in graph.triples((None, RDFS.label, None))
        if (s, RDF.type, SOFT.Class) in graph
    }
    assert "InventoryService" in classes
    assert "BillingService" in classes
    assert "OrderService" in classes

    subgraph, target_uri = prune_subgraph(graph, "procesarOrden")
    assert target_uri is not None
    invoked = list(subgraph.objects(target_uri, SOFT.invokes))
    assert len(invoked) >= 2


def test_dart_translate_e2e() -> None:
    """Verify end-to-end translate() on a Dart file produces Dart abstract class stubs."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_flutter_service.dart"
    output = ontoprune.translate(fixture_path, "procesarOrden", fmt="stubs")

    assert "OntoPrune Contract: Dart Available APIs" in output
    assert "abstract class OrderService" in output
    assert "abstract class InventoryService" in output
    assert "Future<bool> procesarOrden" in output
    assert "reservarStock" in output


def test_java_translate_e2e() -> None:
    """Verify end-to-end translate() on a Java file produces Java interface stubs."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "SampleJavaService.java"
    output = ontoprune.translate(fixture_path, "procesarOrden", fmt="stubs")

    assert "OntoPrune Contract: Java Available APIs" in output
    assert "public interface OrderService" in output
    assert "public interface InventoryService" in output
    assert "boolean procesarOrden" in output
    assert "reservarStock" in output


def test_typescript_translate_e2e() -> None:
    """Verify end-to-end translate() on a TypeScript file produces TS interface stubs."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_ts_service.ts"
    output = ontoprune.translate(fixture_path, "procesarOrden", fmt="stubs")

    assert "OntoPrune Contract: TypeScript Available APIs" in output
    assert "export interface OrderService" in output
    assert "export interface InventoryService" in output
    assert "procesarOrden" in output
    assert "reservarStock" in output
