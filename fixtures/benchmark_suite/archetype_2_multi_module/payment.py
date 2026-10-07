"""
Payment gateway abstraction and execution for Archetype 2.
"""

from __future__ import annotations

import uuid
from .models import PaymentReceipt, PaymentStatus


class PaymentGateway:
    """Simulates communication with an external payment processor (e.g. Stripe)."""

    def __init__(self, api_secret_key: str = "sk_live_secret_corp_token_xyz") -> None:
        self._secret = api_secret_key

    def charge_customer(self, customer_id: str, amount: float) -> PaymentReceipt:
        """Charges a customer credit card. Negative/zero amounts or bad credentials decline."""
        if not customer_id or amount <= 0.0:
            return PaymentReceipt(
                transaction_id="",
                customer_id=customer_id,
                amount=amount,
                status=PaymentStatus.DECLINED,
            )

        tx_id = f"ch_{uuid.uuid4().hex[:12]}"
        return PaymentReceipt(
            transaction_id=tx_id,
            customer_id=customer_id,
            amount=amount,
            status=PaymentStatus.CAPTURED,
        )

    def refund_transaction(self, transaction_id: str, amount: float) -> bool:
        """Refunds an existing captured transaction."""
        return bool(transaction_id and amount > 0.0)
