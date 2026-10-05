from __future__ import annotations

from ..models.invoice import Invoice
from ..models.order import Order, OrderStatus
from ..repositories.order_repo import OrderRepository
from .billing import BillingService
from .inventory import InventoryService


class OrderService:
    """Core domain orchestrator with cross-module dependencies."""

    def __init__(
        self,
        order_repo: OrderRepository,
        inventory_service: InventoryService,
        billing_service: BillingService,
    ) -> None:
        self.order_repo = order_repo
        self.inventory_service = inventory_service
        self.billing_service = billing_service

    def validar_orden(self, order: Order) -> bool:
        """Validate item availability and totals."""
        if not order.items:
            return False
        order.calculate_total()
        return self.inventory_service.verificar_disponibilidad(order.items)

    def procesar_orden(self, order: Order) -> Invoice | None:
        """Process order fulfillment across inventory, repository and billing services."""
        if not self.validar_orden(order):
            self.order_repo.update_status(order.id, OrderStatus.FAILED)
            return None

        reserved = self.inventory_service.reservar_stock(order.items)
        if not reserved:
            self.order_repo.update_status(order.id, OrderStatus.FAILED)
            return None

        self.order_repo.update_status(order.id, OrderStatus.PAID)
        return self.billing_service.emitir_factura(order)
