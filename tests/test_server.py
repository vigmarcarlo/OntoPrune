"""
Unit tests for OntoPrune MCP Server tools.
"""

from pathlib import Path

from ontoprune.server import prune_context, verify_response


def test_mcp_prune_context_tool() -> None:
    fixture_path = str(Path(__file__).parent.parent / "fixtures" / "sample_service.py")
    res = prune_context(file_path=fixture_path, target_symbol="procesar_orden", format="stubs")

    assert "procesar_orden" in res
    assert "emitir_factura" in res
    assert "reservar_stock" in res
    assert "Error" not in res


def test_mcp_prune_context_nonexistent_file() -> None:
    res = prune_context(file_path="nonexistent_file_123.py", target_symbol="foo")
    assert "Error: File 'nonexistent_file_123.py' does not exist." in res


def test_mcp_verify_response_tool_valid() -> None:
    fixture_path = str(Path(__file__).parent.parent / "fixtures" / "sample_service.py")
    valid_code = """
```python
def refactor(order):
    if not self.validar_orden(order):
        return None
    self.reservar_stock(order.items)
    return self.emitir_factura(order)
```
"""
    result = verify_response(
        response_code=valid_code,
        contract_or_file=fixture_path,
        target_symbol="procesar_orden",
    )
    assert result["is_valid"] is True
    assert result["hallucination_count"] == 0
    assert len(result["invalid_calls"]) == 0


def test_mcp_verify_response_tool_with_hallucination() -> None:
    fixture_path = str(Path(__file__).parent.parent / "fixtures" / "sample_service.py")
    invalid_code = """
```python
def bad_impl(order):
    self.send_crypto_payment(order.id)
    self.delete_all_databases()
```
"""
    result = verify_response(
        response_code=invalid_code,
        contract_or_file=fixture_path,
        target_symbol="procesar_orden",
    )
    assert result["is_valid"] is False
    assert result["hallucination_count"] >= 1
    assert "send_crypto_payment" in result["invalid_calls"]
