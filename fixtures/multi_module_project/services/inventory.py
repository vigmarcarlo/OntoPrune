from __future__ import annotations

from ..models.order import OrderItem


class InventoryService:
    """Service responsible for inventory checks and reservations."""

    def __init__(self) -> None:
        self._stock: dict[str, int] = {}

    def verificar_disponibilidad(self, items: list[OrderItem]) -> bool:
        """Verify stock availability for all order items."""
        for item in items:
            if self._stock.get(item.sku, 0) < item.quantity:
                return False
        return True

    def reservar_stock(self, items: list[OrderItem]) -> bool:
        """Reserve inventory for approved items."""
        if not self.verificar_disponibilidad(items):
            return False
        for item in items:
            self._stock[item.sku] -= item.quantity
        return True
