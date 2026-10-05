"""
Unit and integration tests for Flutter / Dart support in OntoPrune.

Covers:
- Multi-file project traversal with pubspec.yaml and package/relative imports
- Cross-file call resolution and dependency graph generation
- Context pruning for Flutter controllers/widgets
- Dart abstract class contract stubs rendering
- Neuro-symbolic contract verification and hallucination detection (ontoprune check)
"""

from pathlib import Path

from rdflib import Namespace

from ontoprune.check import check
from ontoprune.project import ProjectGraph, parse_project_file
from ontoprune.pruner import prune_subgraph
from ontoprune.render import render_contract

REPO = Namespace("https://w3id.org/ontoprune/repo/")
SOFT = Namespace("https://w3id.org/ontoprune/software#")

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "flutter_project"


def test_flutter_project_multimodule_traversal() -> None:
    """Verifies ProjectGraph discovers and parses internal Dart dependencies."""
    entry_file = FIXTURE_DIR / "lib" / "controllers" / "checkout_controller.dart"
    project = ProjectGraph()
    graph = project.parse_project_for_file(entry_file)

    visited_names = {f.name for f in project.visited_files}
    expected_files = {
        "checkout_controller.dart",
        "order_repository.dart",
        "payment_service.dart",
        "order.dart",
        "cart_item.dart",
    }
    assert expected_files.issubset(visited_names), f"Missing files in {visited_names}"

    # Verify external libraries (flutter/material.dart, dart:async) are excluded
    assert not any("material" in f.name for f in project.visited_files)

    # Verify RDF graph contains classes from across the files
    from rdflib import RDF

    classes = {
        str(s).split("#")[-1].split("/")[-1]
        for s, p, o in graph.triples((None, RDF.type, SOFT.Class))
    }
    assert any("CheckoutController" in c for c in classes)
    assert any("IOrderRepository" in c for c in classes)
    assert any("PaymentService" in c for c in classes)


def test_flutter_cross_file_pruning() -> None:
    """Verifies that pruning a Flutter controller target preserves exact cross-file callee APIs."""
    entry_file = FIXTURE_DIR / "lib" / "controllers" / "checkout_controller.dart"
    graph = parse_project_file(entry_file)

    target_uri = REPO["func_CheckoutController.executeCheckout"]
    subgraph, stats = prune_subgraph(graph, target_uri)

    # Should retain 1-hop dependencies
    callees = {str(o) for o in subgraph.objects(target_uri, SOFT.invokes)}
    assert str(REPO["func_IOrderRepository.saveOrder"]) in callees
    assert str(REPO["func_PaymentService.processPayment"]) in callees
    assert str(REPO["func_CartItem.subtotal"]) in callees

    # Should prune unused methods in repository and service
    all_funcs = {str(s) for s, p, o in subgraph.triples((None, None, SOFT.Function))}
    assert str(REPO["func_IOrderRepository.cancelOrder"]) not in all_funcs
    assert str(REPO["func_IOrderRepository.getOrderById"]) not in all_funcs
    assert str(REPO["func_PaymentService.refund"]) not in all_funcs


def test_flutter_stubs_rendering() -> None:
    """Verifies that pruned subgraphs render valid Dart abstract interface contracts."""
    entry_file = FIXTURE_DIR / "lib" / "controllers" / "checkout_controller.dart"
    graph = parse_project_file(entry_file)

    target_uri = REPO["func_CheckoutController.executeCheckout"]
    subgraph, stats = prune_subgraph(graph, target_uri)

    stubs = render_contract(subgraph, target_uri, "stubs")

    assert "// === OntoPrune Contract: Dart Available APIs ===" in stubs
    assert "abstract class IOrderRepository {" in stubs
    assert "saveOrder(" in stubs
    assert "abstract class PaymentService {" in stubs
    assert "processPayment(" in stubs
    assert "abstract class CheckoutController {" in stubs
    assert "executeCheckout(" in stubs

    # Unused methods must not appear
    assert "cancelOrder" not in stubs
    assert "refund" not in stubs


def test_flutter_contract_verification_valid() -> None:
    """Verifies ontoprune check allows compliant Dart code with framework builtins."""
    contract = """
// === OntoPrune Contract: Dart Available APIs ===
abstract class IOrderRepository {
  Future<Order> saveOrder(Order order);
}
abstract class PaymentService {
  Future<PaymentReceipt> processPayment(double amount, String paymentToken);
}
abstract class CheckoutController {
  Future<bool> executeCheckout(List items, String paymentToken);
}
"""
    valid_dart_code = """
```dart
Future<bool> executeCheckout(List items, String paymentToken) async {
  if (items.isEmpty) return false;
  final receipt = await paymentService.processPayment(100.0, paymentToken);
  if (!receipt.success) return false;
  await orderRepository.saveOrder(newOrder);
  notifyListeners();
  return true;
}
```
"""
    violations = check(valid_dart_code, against=contract)
    assert len(violations) == 0, f"Expected 0 violations, got: {violations}"


def test_flutter_contract_verification_hallucinations() -> None:
    """Verifies ontoprune check detects hallucinated API calls in Dart responses."""
    contract = """
// === OntoPrune Contract: Dart Available APIs ===
abstract class IOrderRepository {
  Future<Order> saveOrder(Order order);
}
abstract class PaymentService {
  Future<PaymentReceipt> processPayment(double amount, String paymentToken);
}
abstract class CheckoutController {
  Future<bool> executeCheckout(List items, String paymentToken);
}
"""
    hallucinated_dart_code = """
```dart
Future<bool> executeCheckout(List items, String paymentToken) async {
  // Hallucinated calls not in the ontology contract:
  await securityEngine.bypassTwoFactorAuth(paymentToken);
  await analyticsTracker.sendTelemetryEvent("checkout_attempt");
  
  final receipt = await paymentService.processPayment(100.0, paymentToken);
  await orderRepository.saveOrder(newOrder);
  return true;
}
```
"""
    violations = check(hallucinated_dart_code, against=contract)
    assert "bypassTwoFactorAuth" in violations
    assert "sendTelemetryEvent" in violations
    assert "processPayment" not in violations
    assert "saveOrder" not in violations
