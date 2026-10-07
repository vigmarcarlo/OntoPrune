"""
Archetype 1: Isolated Algorithmic Module.

Evaluates scoring rules, velocity limits, and risk thresholds without external network services.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any


class RiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskAssessment:
    score: float
    level: str
    flagged_reasons: list[str]
    checksum: str


class TransactionRiskEvaluator:
    """Evaluates transaction security and fraud patterns."""

    def __init__(self, max_daily_limit: float = 10000.0, velocity_threshold: int = 5) -> None:
        self.max_daily_limit = max_daily_limit
        self.velocity_threshold = velocity_threshold

    def calculate_checksum(self, transaction_id: str, amount: float, user_id: str) -> str:
        """Calculates SHA256 checksum for payload verification."""
        raw = f"{transaction_id}:{amount:.2f}:{user_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def evaluate_velocity(self, recent_transactions_count: int) -> bool:
        """Returns True if velocity exceeds threshold."""
        return recent_transactions_count > self.velocity_threshold

    def evaluate_transaction(
        self,
        transaction_id: str,
        user_id: str,
        amount: float,
        recent_count: int,
        is_international: bool = False,
    ) -> RiskAssessment:
        """
        Calculates risk score and assigns risk level.
        Base rule:
        - Negative or zero amounts raise ValueError.
        - Exceeding max_daily_limit adds 40 points.
        - High velocity adds 30 points.
        - International adds 20 points.
        - Final score clamped to [0.0, 100.0].
        - >= 80: CRITICAL, >= 50: HIGH, >= 20: MEDIUM, else LOW.
        """
        if amount <= 0.0:
            raise ValueError("Transaction amount must be positive.")

        score = 0.0
        reasons: list[str] = []

        if amount > self.max_daily_limit:
            score += 40.0
            reasons.append("EXCEEDS_DAILY_LIMIT")

        if self.evaluate_velocity(recent_count):
            score += 30.0
            reasons.append("HIGH_VELOCITY_BURST")

        if is_international:
            score += 20.0
            reasons.append("CROSS_BORDER_RISK")

        score = min(100.0, score)

        if score >= 80.0:
            level = RiskLevel.CRITICAL
        elif score >= 50.0:
            level = RiskLevel.HIGH
        elif score >= 20.0:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        checksum = self.calculate_checksum(transaction_id, amount, user_id)
        return RiskAssessment(score=score, level=level, flagged_reasons=reasons, checksum=checksum)
