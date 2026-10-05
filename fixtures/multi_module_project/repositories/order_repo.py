from __future__ import annotations

from ..models.order import Order, OrderStatus
from .base import Repository


class OrderRepository(Repository[Order]):
    """Concrete repository for order persistence."""

    def update_status(self, order_id: str, status: OrderStatus) -> Order | None:
        order = self.find_by_id(order_id)
        if order:
            order.status = status
            return self.save(order_id, order)
        return None
