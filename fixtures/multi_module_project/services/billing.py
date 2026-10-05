from __future__ import annotations

import datetime
import uuid

from ..models.invoice import Invoice
from ..models.order import Order


class BillingService:
    """Service responsible for invoice creation and billing."""

    def emitir_factura(self, order: Order) -> Invoice:
        """Issue an invoice for an approved order."""
        return Invoice(
            id=str(uuid.uuid4()),
            order_id=order.id,
            customer_id=order.customer_id,
            amount=order.total_amount,
            issued_at=datetime.datetime.utcnow(),
            paid=False,
        )
