from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


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

    def calculate_total(self) -> float:
        self.total_amount = sum(item.total_price for item in self.items)
        return self.total_amount
