"""
Unit tests for multi-file and multi-module project import resolution.
"""

from pathlib import Path

from ontoprune import translate
from ontoprune.project import ProjectGraph
from ontoprune.resolver import ImportResolver, find_project_root


def test_find_project_root() -> None:
    fixture_file = (
        Path(__file__).parent.parent
        / "fixtures"
        / "multi_module_project"
        / "services"
        / "order_service.py"
    )
    root = find_project_root(fixture_file)
    assert root.exists()
    assert (root / "pyproject.toml").exists() or (root / ".git").exists()


def test_import_resolver_relative_and_absolute() -> None:
    project_root = Path(__file__).parent.parent / "fixtures" / "multi_module_project"
    resolver = ImportResolver(project_root)

    current_file = project_root / "services" / "order_service.py"

    # Test relative import level 1: from .billing import BillingService
    res_billing = resolver.resolve_import(current_file, module="billing", level=1)
    assert res_billing is not None
    assert res_billing.name == "billing.py"

    # Test relative import level 2: from ..models.order import Order
    res_order = resolver.resolve_import(current_file, module="models.order", level=2)
    assert res_order is not None
    assert res_order.name == "order.py"

    # Test relative import level 2: from ..repositories.order_repo import OrderRepository
    res_repo = resolver.resolve_import(current_file, module="repositories.order_repo", level=2)
    assert res_repo is not None
    assert res_repo.name == "order_repo.py"

    # Test non-existent or external standard library import
    res_ext = resolver.resolve_import(current_file, module="datetime", level=0)
    assert res_ext is None


def test_project_graph_parses_dependencies_recursively() -> None:
    project_root = Path(__file__).parent.parent / "fixtures" / "multi_module_project"
    entry_file = project_root / "services" / "order_service.py"

    project = ProjectGraph(project_root=project_root)
    graph = project.parse_project_for_file(entry_file)

    # Must have visited order_service.py, billing.py, inventory.py, order_repo.py
    visited_names = {f.name for f in project.visited_files}
    assert "order_service.py" in visited_names
    assert "billing.py" in visited_names
    assert "inventory.py" in visited_names
    assert "order_repo.py" in visited_names

    # Graph should contain triples from multiple modules
    assert len(graph) > 100


def test_translate_multi_module_subgraph() -> None:
    """Verify that translate() on a modular file prunes and resolves cross-module invocations."""
    project_root = Path(__file__).parent.parent / "fixtures" / "multi_module_project"
    entry_file = project_root / "services" / "order_service.py"

    contract = translate(
        source_or_file=entry_file,
        target="procesar_orden",
        fmt="stubs",
        multi_module=True,
        project_root=project_root,
    )

    # The pruned stubs must include methods from the other modules!
    # 1. BillingService.emitir_factura (from services/billing.py)
    # 2. InventoryService.reservar_stock (from services/inventory.py)
    # 3. OrderRepository.update_status (from repositories/order_repo.py)
    assert "procesar_orden" in contract
    assert "emitir_factura" in contract
    assert "reservar_stock" in contract
    assert "update_status" in contract
