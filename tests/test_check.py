"""
Unit tests for ontoprune.check contract verification.
"""

from ontoprune.check import check


def test_check_valid_response() -> None:
    contract = """
# === OntoPrune Contract: Available APIs ===
def validar_orden(order: Order) -> bool: ...
def reservar_stock(items: List[OrderItem]) -> bool: ...
def cobrar(customer_id: str, amount: float) -> PaymentReceipt: ...
def emitir_factura(order: Order) -> Invoice: ...
def update_status(order_id: str, status: OrderStatus) -> Optional[Order]: ...
def procesar_orden(order: Order) -> Optional[Invoice]: ...
"""
    valid_llm_code = """
```python
def refactored_procesar(self, order):
    if not self.validar_orden(order):
        return None
    self.reservar_stock(order.items)
    receipt = self.cobrar(order.customer_id, order.total_amount)
    inv = self.emitir_factura(order)
    self.update_status(order.id, "PAID")
    return inv
```
"""
    violations = check(valid_llm_code, against=contract)
    assert len(violations) == 0, f"Expected 0 violations, got: {violations}"


def test_check_detects_hallucinations() -> None:
    contract = """
def validar_orden(order: Order) -> bool: ...
def cobrar(customer_id: str, amount: float) -> PaymentReceipt: ...
"""
    hallucinated_code = """
```python
def handle(self, order):
    # send_sms_alert and execute_blockchain_tx are hallucinated
    self.send_sms_alert(order.customer_id)
    self.execute_blockchain_tx(order.id)
    return self.cobrar(order.customer_id, 100.0)
```
"""
    violations = check(hallucinated_code, against=contract)
    assert "send_sms_alert" in violations
    assert "execute_blockchain_tx" in violations
    assert "cobrar" not in violations
