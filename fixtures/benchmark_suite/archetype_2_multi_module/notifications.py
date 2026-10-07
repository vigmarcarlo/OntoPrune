"""
Notification dispatch for customer events in Archetype 2.
"""

from __future__ import annotations


class CustomerNotifier:
    """Dispatches transactional emails and push notifications."""

    def __init__(self, sender_email: str = "noreply@store.com") -> None:
        self.sender = sender_email
        self.sent_messages: list[dict[str, str]] = []

    def notify_order_approved(self, customer_id: str, invoice_id: str) -> bool:
        """Sends order success confirmation."""
        self.sent_messages.append({"customer_id": customer_id, "type": "APPROVED", "ref": invoice_id})
        return True

    def notify_order_failed(self, customer_id: str, reason: str) -> bool:
        """Sends order failure notification."""
        self.sent_messages.append({"customer_id": customer_id, "type": "FAILED", "reason": reason})
        return True
