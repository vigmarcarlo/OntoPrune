from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass
class Invoice:
    id: str
    order_id: str
    customer_id: str
    amount: float
    issued_at: datetime.datetime
    paid: bool = False
