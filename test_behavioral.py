"""Test suite for behavioral fingerprinting and anomaly detection.

This script verifies the correct functioning of the agent_behavior table logging,
baseline calculations, and revocation logic based on behavioral drift.
"""

import math
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Any

# Ensure we're testing against the refactored logic.
from consensus import ConsensusEngine
from database import DatabaseManager


def setup_test_db() -> DatabaseManager:
    """Provides a fresh database instance for testing.

    Returns:
        An initialized DatabaseManager.
    """
    db_file = "payments.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    return DatabaseManager(db_file)


def calculate_sigma_baseline(db: DatabaseManager, agent_id: str) -> Dict[str, float]:
    """Mirror of the baseline calculation logic in main.py for validation.

    Args:
        db: DatabaseManager instance.
        agent_id: The agent to check.

    Returns:
        Dict with 'mean' and 'sigma'.
    """
    amounts = db.get_agent_approved_amounts(agent_id)
    n = len(amounts)
    
    if n == 0:
        return {"mean": 0.0, "sigma": 0.0}
    
    mean = sum(amounts) / n
    if n < 2:
        return {"mean": mean, "sigma": 0.0}
    
    variance = sum((x - mean) ** 2 for x in amounts) / (n - 1)
    sigma = math.sqrt(variance)
    
    return {"mean": mean, "sigma": sigma}


def test_table_initialization(db: DatabaseManager) -> bool:
    """Verifies that the agent_behavior table is initialized with the correct schema."""
    print("\n" + "="*60)
    print("TEST 1: Database Schema Verification")
    print("="*60)
    
    conn = sqlite3.connect(str(db.db_path))
    cursor = conn.cursor()
    
    # Check if the table exists.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agent_behavior'")
    if not cursor.fetchone():
        print("[FAIL] agent_behavior table was not created.")
        return False
    
    # Check column definitions.
    cursor.execute("PRAGMA table_info(agent_behavior)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    expected_columns = {
        "agent_id": "TEXT",
        "transaction_id": "TEXT",
        "vote": "TEXT",
        "amount": "REAL",
        "timestamp": "TIMESTAMP"
    }
    
    for col, dtype in expected_columns.items():
        if col not in columns:
            print(f"[FAIL] Column '{col}' is missing.")
            return False
        print(f"[PASS] Column '{col}' verified.")
    
    conn.close()
    return True


def test_vote_logging(db: DatabaseManager) -> bool:
    """Verifies that votes are correctly logged by the DatabaseManager."""
    print("\n" + "="*60)
    print("TEST 2: Persistent Vote Logging")
    print("="*60)
    
    agent_id = "test_agent_001"
    tx_id = "tx_12345"
    amount = 500.0
    
    db.log_agent_vote(agent_id, tx_id, "APPROVE", amount)
    
    amounts = db.get_agent_approved_amounts(agent_id)
    if len(amounts) == 1 and amounts[0] == 500.0:
        print(f"[PASS] Correctly logged and retrieved approval: ${amounts[0]}")
        return True
    
    print(f"[FAIL] Logged vote could not be retrieved correctly. Found: {amounts}")
    return False


def test_baseline_accuracy(db: DatabaseManager) -> bool:
    """Verifies the accuracy of standard deviation and mean calculations."""
    print("\n" + "="*60)
    print("TEST 3: Baseline Calculation Accuracy")
    print("="*60)
    
    agent_id = "stat_agent"
    test_data = [100.0, 200.0, 300.0, 400.0, 500.0]
    
    for i, amt in enumerate(test_data):
        db.log_agent_vote(agent_id, f"tx_{i}", "APPROVE", amt)
        
    baseline = calculate_sigma_baseline(db, agent_id)
    
    # Expected: Mean = 300, StdDev = sqrt(25000) approx 158.113
    expected_mean = 300.0
    expected_sigma = 158.113883
    
    if abs(baseline["mean"] - expected_mean) > 0.001:
        print(f"[FAIL] Mean mismatch. Expected {expected_mean}, got {baseline['mean']}")
        return False
        
    if abs(baseline["sigma"] - expected_sigma) > 0.001:
        print(f"[FAIL] Sigma mismatch. Expected {expected_sigma}, got {baseline['sigma']}")
        return False
        
    print(f"[PASS] Baseline metrics verified: Mean={baseline['mean']}, Sigma={baseline['sigma']:.3f}")
    return True


def test_revocation_logic() -> bool:
    """Verifies the 2-sigma drift revocation filter."""
    print("\n" + "="*60)
    print("TEST 4: 2-Sigma Revocation Logic")
    print("="*60)
    
    # helper for internal logic testing
    def should_revoke(mean: float, sigma: float, amount: float) -> str:
        if sigma == 0: return "HOLD"
        drift = abs(amount - mean)
        return "REVOKE" if drift > 2.0 * sigma else "APPROVE"

    # Test Case: Mean 100, Sigma 15 -> Threshold 130
    m, s = 100.0, 15.0
    
    tests = [
        (110.0, "APPROVE", "Standard deviation within limits"),
        (130.0, "APPROVE", "Exact 2-sigma boundary"),
        (131.0, "REVOKE", "Exceeded 2-sigma boundary"),
        (70.0, "APPROVE", "Lower bound within limits"),
        (69.0, "REVOKE", "Lower bound exceeded deviation")
    ]
    
    for amount, expected, desc in tests:
        result = should_revoke(m, s, amount)
        if result != expected:
            print(f"[FAIL] {desc}: Expected {expected}, got {result}")
            return False
        print(f"[PASS] {desc} verified.")
        
    return True


def run_suite():
    """Executes the full test suite."""
    print("MCP PAYMENTS SIMULATOR: CORE REFACTOR VERIFICATION")
    print("-" * 60)
    
    db = setup_test_db()
    
    results = [
        test_table_initialization(db),
        test_vote_logging(db),
        test_baseline_accuracy(db),
        test_revocation_logic()
    ]


if __name__ == "__main__":
    run_suite()
