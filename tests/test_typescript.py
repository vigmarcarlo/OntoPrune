"""
Unit and integration tests for TypeScript / JavaScript (Node / React) support in OntoPrune.

Covers:
- Multi-file project traversal with package.json and relative imports (.ts, .tsx, .js)
- Cross-file call resolution and dependency graph generation for TypeScript classes, interfaces, and parameter properties
- Context pruning for web/fullstack services (isolating logic, pruning React UI components)
- TypeScript interface contract stubs rendering (export interface ...)
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

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "ts_project"


def test_ts_project_multimodule_traversal() -> None:
    """Verifies ProjectGraph discovers and parses internal TypeScript dependencies."""
    entry_file = FIXTURE_DIR / "src" / "services" / "checkoutService.ts"
    project = ProjectGraph()
    graph = project.parse_project_for_file(entry_file)

    visited_names = {f.name for f in project.visited_files}
    expected_files = {
        "checkoutService.ts",
        "orderRepository.ts",
        "paymentService.ts",
        "order.ts",
    }
    assert expected_files.issubset(visited_names), f"Missing files in {visited_names}"

    # Verify external libraries (react) are excluded
    assert not any("react" in f.name.lower() for f in project.visited_files)

    # Verify RDF graph contains classes from across the files
    classes = {
        str(s).split("#")[-1].split("/")[-1]
        for s, p, o in graph.triples((None, RDF.type, SOFT.Class))
    }
    assert any("CheckoutService" in c for c in classes)
    assert any("IOrderRepository" in c for c in classes)
    assert any("PaymentService" in c for c in classes)


def test_ts_cross_file_pruning() -> None:
    """Verifies that pruning a TypeScript service target preserves exact cross-file callee APIs."""
    entry_file = FIXTURE_DIR / "src" / "services" / "checkoutService.ts"
    graph = parse_project_file(entry_file)

    target_uri = REPO["func_CheckoutService.processCheckout"]
    subgraph, stats = prune_subgraph(graph, target_uri)

    # Should retain 1-hop dependencies
    callees = {str(o) for o in subgraph.objects(target_uri, SOFT.invokes)}
    assert str(REPO["func_IOrderRepository.save"]) in callees
    assert str(REPO["func_PaymentService.charge"]) in callees

    # Should prune unused methods in repository and service
    all_funcs = {str(s) for s, p, o in subgraph.triples((None, None, SOFT.Function))}
    assert str(REPO["func_IOrderRepository.findById"]) not in all_funcs
    assert str(REPO["func_IOrderRepository.delete"]) not in all_funcs
    assert str(REPO["func_PaymentService.refund"]) not in all_funcs


def test_ts_stubs_rendering() -> None:
    """Verifies that pruned TypeScript subgraphs render valid export interface contracts."""
    entry_file = FIXTURE_DIR / "src" / "services" / "checkoutService.ts"
    graph = parse_project_file(entry_file)

    target_uri = REPO["func_CheckoutService.processCheckout"]
    subgraph, stats = prune_subgraph(graph, target_uri)

    stubs = render_contract(subgraph, target_uri, "stubs")

    assert "// === OntoPrune Contract: TypeScript Available APIs ===" in stubs
    assert "export interface IOrderRepository {" in stubs
    assert "save(" in stubs
    assert "export interface PaymentService {" in stubs
    assert "charge(" in stubs
    assert "export interface CheckoutService {" in stubs
    assert "processCheckout(" in stubs

    # Unused methods must not appear
    assert "findById" not in stubs
    assert "refund" not in stubs


def test_ts_contract_verification_valid() -> None:
    """Verifies ontoprune check allows compliant TypeScript code with standard JS methods."""
    contract = """
// === OntoPrune Contract: TypeScript Available APIs ===
export interface IOrderRepository {
    save(order: Order): Promise<Order>;
}
export interface PaymentService {
    charge(amount: number, token: string): Promise<PaymentReceipt>;
}
export interface CheckoutService {
    processCheckout(order: Order, token: string): Promise<boolean>;
}
"""
    valid_ts_code = """
```typescript
export class CheckoutService {
    async processCheckout(order: Order, token: string): Promise<boolean> {
        if (!order || order.total <= 0) {
            return false;
        }
        const receipt = await this.paymentService.charge(order.total, token);
        if (!receipt.successful) {
            return false;
        }
        await this.orderRepo.save(order);
        return true;
    }
}
```
"""
    violations = check(valid_ts_code, against=contract)
    assert len(violations) == 0, f"Expected 0 violations, got: {violations}"


def test_ts_contract_verification_hallucinations() -> None:
    """Verifies ontoprune check detects hallucinated API calls in TypeScript responses."""
    contract = """
// === OntoPrune Contract: TypeScript Available APIs ===
export interface IOrderRepository {
    save(order: Order): Promise<Order>;
}
export interface PaymentService {
    charge(amount: number, token: string): Promise<PaymentReceipt>;
}
export interface CheckoutService {
    processCheckout(order: Order, token: string): Promise<boolean>;
}
"""
    hallucinated_ts_code = """
```typescript
export class CheckoutService {
    async processCheckout(order: Order, token: string): Promise<boolean> {
        // Hallucinated calls not in the ontology contract:
        await this.orderRepo.executeDirectRawQuery("DROP TABLE orders");
        analytics.sendTrackingTelemetry("checkout_click");

        await this.orderRepo.save(order);
        return true;
    }
}
```
"""
    violations = check(hallucinated_ts_code, against=contract)
    assert "executeDirectRawQuery" in violations
    assert "sendTrackingTelemetry" in violations
    assert "save" not in violations
    assert "charge" not in violations
