"""
Unit and integration tests for Java / Spring Boot support in OntoPrune.

Covers:
- Multi-file project traversal with pom.xml and package imports
- Cross-file call resolution and dependency graph generation for Spring @Service / interfaces
- Context pruning for enterprise Java services
- Java interface contract stubs rendering
- Neuro-symbolic contract verification and hallucination detection (ontoprune check)
"""

from pathlib import Path

from rdflib import RDF, Namespace

from ontoprune.check import check
from ontoprune.project import ProjectGraph, parse_project_file
from ontoprune.pruner import prune_subgraph
from ontoprune.render import render_contract

REPO = Namespace("https://w3id.org/ontoprune/repo/")
SOFT = Namespace("https://w3id.org/ontoprune/software#")

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "spring_project"


def test_java_project_multimodule_traversal() -> None:
    """Verifies ProjectGraph discovers and parses internal Java dependencies from a Spring project."""
    entry_file = (
        FIXTURE_DIR / "src" / "main" / "java" / "com" / "shop" / "service" / "CheckoutService.java"
    )
    project = ProjectGraph()
    graph = project.parse_project_for_file(entry_file)

    visited_names = {f.name for f in project.visited_files}
    expected_files = {
        "CheckoutService.java",
        "OrderRepository.java",
        "PaymentGateway.java",
        "Order.java",
        "PaymentReceipt.java",
    }
    assert expected_files.issubset(visited_names), f"Missing files in {visited_names}"

    # Verify external libraries (spring, java.util) are excluded
    assert not any("spring" in f.name.lower() for f in project.visited_files)

    # Verify RDF graph contains classes from across the files
    classes = {
        str(s).split("#")[-1].split("/")[-1]
        for s, p, o in graph.triples((None, RDF.type, SOFT.Class))
    }
    assert any("CheckoutService" in c for c in classes)
    assert any("OrderRepository" in c for c in classes)
    assert any("PaymentGateway" in c for c in classes)


def test_java_cross_file_pruning() -> None:
    """Verifies that pruning a Java service target preserves exact cross-file callee APIs."""
    entry_file = (
        FIXTURE_DIR / "src" / "main" / "java" / "com" / "shop" / "service" / "CheckoutService.java"
    )
    graph = parse_project_file(entry_file)

    target_uri = REPO["func_CheckoutService.processCheckout"]
    subgraph, stats = prune_subgraph(graph, target_uri)

    # Should retain 1-hop dependencies
    callees = {str(o) for o in subgraph.objects(target_uri, SOFT.invokes)}
    assert str(REPO["func_OrderRepository.save"]) in callees
    assert str(REPO["func_PaymentGateway.charge"]) in callees
    assert str(REPO["func_Order.getTotalAmount"]) in callees
    assert str(REPO["func_PaymentReceipt.isSuccessful"]) in callees

    # Should prune unused methods in repository and service
    all_funcs = {str(s) for s, p, o in subgraph.triples((None, None, SOFT.Function))}
    assert str(REPO["func_OrderRepository.findById"]) not in all_funcs
    assert str(REPO["func_OrderRepository.delete"]) not in all_funcs
    assert str(REPO["func_PaymentGateway.refund"]) not in all_funcs


def test_java_stubs_rendering() -> None:
    """Verifies that pruned Java subgraphs render valid public interface contracts."""
    entry_file = (
        FIXTURE_DIR / "src" / "main" / "java" / "com" / "shop" / "service" / "CheckoutService.java"
    )
    graph = parse_project_file(entry_file)

    target_uri = REPO["func_CheckoutService.processCheckout"]
    subgraph, stats = prune_subgraph(graph, target_uri)

    stubs = render_contract(subgraph, target_uri, "stubs")

    assert "// === OntoPrune Contract: Java Available APIs ===" in stubs
    assert "public interface OrderRepository {" in stubs
    assert "save(" in stubs
    assert "public interface PaymentGateway {" in stubs
    assert "charge(" in stubs
    assert "public interface CheckoutService {" in stubs
    assert "processCheckout(" in stubs

    # Unused methods must not appear
    assert "findById" not in stubs
    assert "refund" not in stubs


def test_java_contract_verification_valid() -> None:
    """Verifies ontoprune check allows compliant Java code with standard methods."""
    contract = """
// === OntoPrune Contract: Java Available APIs ===
public interface Order {
    double getTotalAmount();
}
public interface PaymentReceipt {
    boolean isSuccessful();
}
public interface OrderRepository {
    Order save(Order order);
}
public interface PaymentGateway {
    PaymentReceipt charge(double amount, String paymentToken);
}
public interface CheckoutService {
    boolean processCheckout(Order order, String token);
}
"""
    valid_java_code = """
```java
public class CheckoutService {
    public boolean processCheckout(Order order, String token) {
        if (order == null || order.getTotalAmount() <= 0) {
            return false;
        }
        PaymentReceipt receipt = paymentGateway.charge(order.getTotalAmount(), token);
        if (!receipt.isSuccessful()) {
            return false;
        }
        orderRepository.save(order);
        return true;
    }
}
```
"""
    violations = check(valid_java_code, against=contract)
    assert len(violations) == 0, f"Expected 0 violations, got: {violations}"


def test_java_contract_verification_hallucinations() -> None:
    """Verifies ontoprune check detects hallucinated API calls in Java responses."""
    contract = """
// === OntoPrune Contract: Java Available APIs ===
public interface OrderRepository {
    Order save(Order order);
}
public interface PaymentGateway {
    PaymentReceipt charge(double amount, String paymentToken);
}
public interface CheckoutService {
    boolean processCheckout(Order order, String token);
}
"""
    hallucinated_java_code = """
```java
public class CheckoutService {
    public boolean processCheckout(Order order, String token) {
        // Hallucinated calls not in the ontology contract:
        orderRepository.executeDirectQuery("DELETE FROM audit_log");
        notificationBroker.sendJmsMessage("order_received");

        orderRepository.save(order);
        return true;
    }
}
```
"""
    violations = check(hallucinated_java_code, against=contract)
    assert "executeDirectQuery" in violations
    assert "sendJmsMessage" in violations
    assert "save" not in violations
