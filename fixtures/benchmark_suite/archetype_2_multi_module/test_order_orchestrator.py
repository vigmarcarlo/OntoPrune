"""
Unit tests for Archetype 2: OrderOrchestrator.
"""

from unittest.mock import MagicMock
import pytest

from .inventory import InventoryRepository
from .models import Order, OrderItem, OrderStatus, PaymentReceipt, PaymentStatus
from .notifications import CustomerNotifier
from .order_orchestrator import OrderOrchestrator
from .payment import PaymentGateway


@pytest.fixture
def orchestrator():
    inv = InventoryRepository({"SKU-A": 10, "SKU-B": 5})
    pay = PaymentGateway()
    notifier = CustomerNotifier()
    return OrderOrchestrator(inventory=inv, payment=pay, notifier=notifier)


def test_checkout_successful_flow(orchestrator):
    order = Order(
        id="ord_1",
        customer_id="cust_1",
        items=[OrderItem("SKU-A", 2, 50.0), OrderItem("SKU-B", 1, 100.0)],
    )
    invoice = orchestrator.process_order_checkout(order)

    assert invoice is not None
    assert invoice.order_id == "ord_1"
    assert invoice.total_amount == 200.0
    assert order.status == OrderStatus.PAID
    assert orchestrator.inventory._stock["SKU-A"] == 8
    assert orchestrator.inventory._stock["SKU-B"] == 4
    assert len(orchestrator.notifier.sent_messages) == 1
    assert orchestrator.notifier.sent_messages[0]["type"] == "APPROVED"


def test_checkout_fails_when_no_items(orchestrator):
    order = Order(id="ord_2", customer_id="cust_1", items=[])
    invoice = orchestrator.process_order_checkout(order)

    assert invoice is None
    assert order.status == OrderStatus.FAILED
    assert len(orchestrator.notifier.sent_messages) == 1
    assert orchestrator.notifier.sent_messages[0]["type"] == "FAILED"


def test_checkout_fails_on_insufficient_stock(orchestrator):
    order = Order(
        id="ord_3",
        customer_id="cust_2",
        items=[OrderItem("SKU-A", 20, 10.0)],  # Only 10 available
    )
    invoice = orchestrator.process_order_checkout(order)

    assert invoice is None
    assert order.status == OrderStatus.FAILED
    assert orchestrator.inventory._stock["SKU-A"] == 10  # Stock untouched


def test_checkout_rollback_stock_when_payment_declined():
    inv = InventoryRepository({"SKU-A": 10})
    pay = MagicMock(spec=PaymentGateway)
    pay.charge_customer.return_value = PaymentReceipt(
        transaction_id="", customer_id="cust_x", amount=100.0, status=PaymentStatus.DECLINED
    )
    notifier = CustomerNotifier()
    orch = OrderOrchestrator(inventory=inv, payment=pay, notifier=notifier)

    order = Order(id="ord_4", customer_id="cust_x", items=[OrderItem("SKU-A", 2, 50.0)])
    invoice = orch.process_order_checkout(order)

    assert invoice is None
    assert order.status == OrderStatus.FAILED
    # Stock must have rolled back to 10
    assert inv._stock["SKU-A"] == 10
    assert len(notifier.sent_messages) == 1
    assert notifier.sent_messages[0]["type"] == "FAILED"


def test_validation_fails_for_zero_total_amount(orchestrator):
    order = Order(id="ord_5", customer_id="cust_1", items=[OrderItem("SKU-A", 1, 0.0)])
    invoice = orchestrator.process_order_checkout(order)

    assert invoice is None
    assert order.status == OrderStatus.FAILED


def test_inventory_atomic_deduction(orchestrator):
    order = Order(id="ord_6", customer_id="cust_1", items=[OrderItem("SKU-B", 5, 20.0)])
    invoice = orchestrator.process_order_checkout(order)

    assert invoice is not None
    assert orchestrator.inventory._stock["SKU-B"] == 0
    # Next identical order must fail
    order2 = Order(id="ord_7", customer_id="cust_1", items=[OrderItem("SKU-B", 1, 20.0)])
    assert orchestrator.process_order_checkout(order2) is None


def test_order_registry_tracks_instances(orchestrator):
    order = Order(id="ord_track", customer_id="cust_1", items=[OrderItem("SKU-A", 1, 10.0)])
    orchestrator.process_order_checkout(order)
    assert "ord_track" in orchestrator.orders


def test_notification_includes_generated_invoice_ref(orchestrator):
    order = Order(id="ord_ref", customer_id="cust_1", items=[OrderItem("SKU-A", 1, 10.0)])
    inv = orchestrator.process_order_checkout(order)
    msg = orchestrator.notifier.sent_messages[-1]
    assert msg["ref"] == inv.invoice_id
