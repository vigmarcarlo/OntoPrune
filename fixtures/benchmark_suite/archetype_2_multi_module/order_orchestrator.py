"""
Order orchestrator service: target of Archetype 2 evaluation.
"""

from __future__ import annotations

import uuid
from .inventory import InventoryRepository
from .models import Invoice, Order, OrderStatus, PaymentStatus
from .notifications import CustomerNotifier
from .payment import PaymentGateway


class OrderOrchestrator:
    """Core domain service orchestrating payment, stock, and customer notifications."""

    def __init__(
        self,
        inventory: InventoryRepository,
        payment: PaymentGateway,
        notifier: CustomerNotifier,
    ) -> None:
        self.inventory = inventory
        self.payment = payment
        self.notifier = notifier
        self.orders: dict[str, Order] = {}

    def validate_order(self, order: Order) -> bool:
        """Validates items existence and stock availability."""
        if not order.items:
            return False
        order.compute_total()
        if order.total_amount <= 0.0:
            return False
        return self.inventory.has_sufficient_stock(order.items)

    def process_order_checkout(self, order: Order) -> Invoice | None:
        """
        Executes order fulfillment protocol:
        1. Validate items and stock availability.
        2. Reserve stock in inventory. If failure, mark order FAILED.
        3. Charge customer via payment gateway.
           If payment declined, rollback reserved stock, notify failure, mark order FAILED.
        4. If payment succeeded, mark order PAID, notify customer, issue invoice.
        """
        self.orders[order.id] = order

        if not self.validate_order(order):
            order.status = OrderStatus.FAILED
            self.notifier.notify_order_failed(order.customer_id, "Stock o items invalidos")
            return None

        if not self.inventory.lock_and_reserve(order.items):
            order.status = OrderStatus.FAILED
            self.notifier.notify_order_failed(order.customer_id, "Fallo al reservar stock")
            return None

        receipt = self.payment.charge_customer(order.customer_id, order.total_amount)
        if receipt.status != PaymentStatus.CAPTURED:
            self.inventory.release_reserved_stock(order.items)
            order.status = OrderStatus.FAILED
            self.notifier.notify_order_failed(order.customer_id, "Pago declinado")
            return None

        order.status = OrderStatus.PAID
        inv_id = f"inv_{uuid.uuid4().hex[:8]}"
        invoice = Invoice(invoice_id=inv_id, order_id=order.id, total_amount=order.total_amount)
        self.notifier.notify_order_approved(order.customer_id, inv_id)
        return invoice
