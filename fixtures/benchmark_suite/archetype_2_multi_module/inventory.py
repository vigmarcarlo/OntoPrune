"""
Inventory service and stock management for Archetype 2.
"""

from __future__ import annotations

from .models import OrderItem


class InventoryRepository:
    """Manages stock level checks, reservations, and rollbacks."""

    def __init__(self, initial_stock: dict[str, int] | None = None) -> None:
        self._stock: dict[str, int] = initial_stock or {}

    def has_sufficient_stock(self, items: list[OrderItem]) -> bool:
        """Returns True if all requested SKUs meet quantity requirements."""
        if not items:
            return False
        for item in items:
            available = self._stock.get(item.sku, 0)
            if available < item.quantity:
                return False
        return True

    def lock_and_reserve(self, items: list[OrderItem]) -> bool:
        """Atomically deducts items from inventory if available."""
        if not self.has_sufficient_stock(items):
            return False
        for item in items:
            self._stock[item.sku] -= item.quantity
        return True

    def release_reserved_stock(self, items: list[OrderItem]) -> None:
        """Rolls back reservations upon checkout failure."""
        for item in items:
            self._stock[item.sku] = self._stock.get(item.sku, 0) + item.quantity
