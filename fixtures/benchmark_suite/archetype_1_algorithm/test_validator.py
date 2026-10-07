"""
Unit tests for Archetype 1: TransactionRiskEvaluator.
"""

import pytest
from validator import RiskLevel, TransactionRiskEvaluator


def test_low_risk_transaction():
    evaluator = TransactionRiskEvaluator(max_daily_limit=5000.0, velocity_threshold=5)
    res = evaluator.evaluate_transaction("tx1", "usr1", 100.0, recent_count=2, is_international=False)
    assert res.score == 0.0
    assert res.level == RiskLevel.LOW
    assert len(res.flagged_reasons) == 0
    assert len(res.checksum) == 64


def test_velocity_and_international_risk():
    evaluator = TransactionRiskEvaluator(max_daily_limit=5000.0, velocity_threshold=3)
    res = evaluator.evaluate_transaction("tx2", "usr1", 500.0, recent_count=4, is_international=True)
    assert res.score == 50.0
    assert res.level == RiskLevel.HIGH
    assert "HIGH_VELOCITY_BURST" in res.flagged_reasons
    assert "CROSS_BORDER_RISK" in res.flagged_reasons


def test_critical_risk_all_flags():
    evaluator = TransactionRiskEvaluator(max_daily_limit=1000.0, velocity_threshold=2)
    res = evaluator.evaluate_transaction("tx3", "usr2", 2000.0, recent_count=5, is_international=True)
    assert res.score == 90.0
    assert res.level == RiskLevel.CRITICAL
    assert len(res.flagged_reasons) == 3


def test_invalid_negative_amount_raises():
    evaluator = TransactionRiskEvaluator()
    with pytest.raises(ValueError, match="positive"):
        evaluator.evaluate_transaction("tx4", "usr1", -50.0, recent_count=1)


def test_checksum_consistency():
    evaluator = TransactionRiskEvaluator()
    c1 = evaluator.calculate_checksum("tx_same", 150.0, "usr_x")
    c2 = evaluator.calculate_checksum("tx_same", 150.0, "usr_x")
    assert c1 == c2
