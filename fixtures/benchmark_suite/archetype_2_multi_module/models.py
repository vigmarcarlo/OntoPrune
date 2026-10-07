"""
Domain models for Archetype 2: Multi-Module Order Processing.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentStatus(str, Enum):
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    DECLINED = "declined"
    REFUNDED = "refunded"


@dataclass
class OrderItem:
    sku: str
    quantity: int
    unit_price: float

    @property
    def subtotal(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Order:
    id: str
    customer_id: str
    items: list[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    total_amount: float = 0.0

    def compute_total(self) -> float:
        self.total_amount = sum(item.subtotal for item in self.items)
        return self.total_amount


@dataclass
class PaymentReceipt:
    transaction_id: str
    customer_id: str
    amount: float
    status: PaymentStatus
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.utcnow)


@dataclass
class Invoice:
    invoice_id: str
    order_id: str
    total_amount: float
    issued_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
