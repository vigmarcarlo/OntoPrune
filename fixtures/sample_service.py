"""
Sample E-Commerce Order & Billing Service Fixture.

This module simulates a realistic multi-component Python service
with inheritance, dataclasses, cross-class dependencies, and method name overlaps.
It serves as the evaluation target for OntoPrune's AST parser and semantic pruning.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar


class OrderStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    DECLINED = "declined"
    REFUNDED = "refunded"


@dataclass
class Customer:
    id: str
    name: str
    email: str
    is_vip: bool = False
    credit_limit: float = 5000.0


@dataclass
class OrderItem:
    sku: str
    quantity: int
    unit_price: float

    @property
    def total_price(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Order:
    id: str
    customer_id: str
    items: list[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    total_amount: float = 0.0
    created_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    notes: str | None = None

    def calculate_total(self) -> float:
        self.total_amount = sum(item.total_price for item in self.items)
        return self.total_amount


@dataclass
class Invoice:
    id: str
    order_id: str
    customer_id: str
    amount: float
    issued_at: datetime.datetime
    paid: bool = False


@dataclass
class PaymentReceipt:
    transaction_id: str
    order_id: str
    amount: float
    status: PaymentStatus
    timestamp: datetime.datetime


T = TypeVar("T")


class Repository(Generic[T]):
    """Generic repository interface."""

    def __init__(self) -> None:
        self._storage: dict[str, T] = {}

    def save(self, entity_id: str, entity: T) -> T:
        """Persist entity to internal store."""
        self._storage[entity_id] = entity
        return entity

    def find_by_id(self, entity_id: str) -> T | None:
        """Retrieve entity by identifier."""
        return self._storage.get(entity_id)

    def delete(self, entity_id: str) -> bool:
        """Delete entity by identifier."""
        if entity_id in self._storage:
            del self._storage[entity_id]
            return True
        return False


class OrderRepository(Repository[Order]):
    """Concrete repository for orders."""

    def find_by_customer(self, customer_id: str) -> list[Order]:
        return [order for order in self._storage.values() if order.customer_id == customer_id]

    def update_status(self, order_id: str, status: OrderStatus) -> Order | None:
        order = self.find_by_id(order_id)
        if order:
            order.status = status
            return self.save(order_id, order)
        return None


class InvoiceRepository(Repository[Invoice]):
    """Concrete repository for invoices."""

    def find_unpaid(self) -> list[Invoice]:
        return [inv for inv in self._storage.values() if not inv.paid]

    def mark_as_paid(self, invoice_id: str) -> Invoice | None:
        invoice = self.find_by_id(invoice_id)
        if invoice:
            invoice.paid = True
            return self.save(invoice_id, invoice)
        return None


class BaseService:
    """Base class for domain application services."""

    def __init__(self, service_name: str) -> None:
        self.service_name = service_name

    def log_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """Log structured audit event."""
        print(f"[{self.service_name}] {event_name}: {payload}")

    @staticmethod
    def generate_token() -> str:
        """Generate unique transaction token."""
        return str(uuid.uuid4())


class InventoryService(BaseService):
    """Inventory control service."""

    def __init__(self) -> None:
        super().__init__("InventoryService")
        self._stock: dict[str, int] = {}

    def set_stock(self, sku: str, quantity: int) -> None:
        self._stock[sku] = quantity

    def verificar_disponibilidad(self, items: list[OrderItem]) -> bool:
        """Check if all requested items are in stock."""
        for item in items:
            available = self._stock.get(item.sku, 0)
            if available < item.quantity:
                return False
        return True

    def reservar_stock(self, items: list[OrderItem]) -> bool:
        """Reserve inventory for approved order."""
        if not self.verificar_disponibilidad(items):
            return False
        for item in items:
            self._stock[item.sku] -= item.quantity
        return True


class PaymentGateway(BaseService):
    """External payment processor abstraction."""

    def __init__(self, api_key: str) -> None:
        super().__init__("PaymentGateway")
        self.api_key = api_key

    def cobrar(self, customer_id: str, amount: float) -> PaymentReceipt:
        """Process charge through payment rail."""
        self.log_event("charge_attempt", {"customer_id": customer_id, "amount": amount})
        tx_id = self.generate_token()
        # Simulated success
        return PaymentReceipt(
            transaction_id=tx_id,
            order_id="",
            amount=amount,
            status=PaymentStatus.CAPTURED,
            timestamp=datetime.datetime.utcnow(),
        )

    def reembolsar(self, transaction_id: str, amount: float) -> bool:
        """Refund previous charge."""
        self.log_event("refund_attempt", {"tx": transaction_id, "amount": amount})
        return True


class BillingService(BaseService):
    """Invoicing and financial reporting service."""

    def __init__(self, invoice_repo: InvoiceRepository) -> None:
        super().__init__("BillingService")
        self.invoice_repo = invoice_repo

    def emitir_factura(self, order: Order) -> Invoice:
        """Create and persist invoice for given order."""
        invoice = Invoice(
            id=self.generate_token(),
            order_id=order.id,
            customer_id=order.customer_id,
            amount=order.total_amount,
            issued_at=datetime.datetime.utcnow(),
            paid=False,
        )
        self.invoice_repo.save(invoice.id, invoice)
        self.log_event("invoice_issued", {"invoice_id": invoice.id, "order_id": order.id})
        return invoice


class NotificationService(BaseService):
    """Customer alerting and notification service."""

    def __init__(self) -> None:
        super().__init__("NotificationService")

    def notificar_cliente(self, customer_id: str, mensaje: str) -> bool:
        """Send notification message to customer."""
        self.log_event("notification_sent", {"customer_id": customer_id, "msg": mensaje})
        return True


class OrderService(BaseService):
    """Core domain orchestrator for order processing workflows."""

    def __init__(
        self,
        order_repo: OrderRepository,
        inventory_service: InventoryService,
        payment_gateway: PaymentGateway,
        billing_service: BillingService,
        notification_service: NotificationService,
    ) -> None:
        super().__init__("OrderService")
        self.order_repo = order_repo
        self.inventory_service = inventory_service
        self.payment_gateway = payment_gateway
        self.billing_service = billing_service
        self.notification_service = notification_service

    def validar_orden(self, order: Order) -> bool:
        """Validate order data and customer inventory constraints."""
        if not order.items:
            return False
        order.calculate_total()
        if order.total_amount <= 0.0:
            return False
        return self.inventory_service.verificar_disponibilidad(order.items)

    def procesar_orden(self, order: Order) -> Invoice | None:
        """
        Process and fulfill an incoming customer order.
        Validates inventory, authorizes payment, updates status, and issues invoice.
        """
        self.log_event("order_processing_started", {"order_id": order.id})

        # Step 1: Validation
        if not self.validar_orden(order):
            self.order_repo.update_status(order.id, OrderStatus.FAILED)
            self.notification_service.notificar_cliente(
                order.customer_id, "Orden rechazada por validacion"
            )
            return None

        # Step 2: Inventory reservation
        reserved = self.inventory_service.reservar_stock(order.items)
        if not reserved:
            self.order_repo.update_status(order.id, OrderStatus.FAILED)
            return None

        # Step 3: Payment execution
        receipt = self.payment_gateway.cobrar(order.customer_id, order.total_amount)
        if receipt.status != PaymentStatus.CAPTURED:
            self.order_repo.update_status(order.id, OrderStatus.FAILED)
            return None

        # Step 4: State update and invoicing
        self.order_repo.update_status(order.id, OrderStatus.PAID)
        invoice = self.billing_service.emitir_factura(order)
        self.notification_service.notificar_cliente(
            order.customer_id, f"Orden aprobada. Factura: {invoice.id}"
        )
        return invoice

    def cancelar_orden(self, order_id: str, motivo: str) -> bool:
        """Cancel pending order and notify customer."""
        order = self.order_repo.find_by_id(order_id)
        if not order:
            return False
        if order.status == OrderStatus.PAID:
            return False
        self.order_repo.update_status(order_id, OrderStatus.CANCELLED)
        self.notification_service.notificar_cliente(order.customer_id, f"Orden cancelada: {motivo}")
        return True


def helper_standalone_audit(target_id: str) -> bool:
    """Module-level standalone helper function."""
    return len(target_id) > 0
