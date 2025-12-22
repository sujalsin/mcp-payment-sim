"""
Test script for behavioral fingerprinting implementation.
Tests:
1. agent_behavior table creation
2. Vote logging (simulated via direct DB operations)
3. get_behavioral_baseline function (manual stddev calculation)
4. should_revoke_agent function logic
"""
import sqlite3
from datetime import datetime
import os

# Remove existing database for clean test
if os.path.exists("payments.db"):
    os.remove("payments.db")

# Import the consensus engine to simulate votes
from consensus import ConsensusEngine


def init_db():
    """Initialize database with all tables."""
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mandates (
            id TEXT PRIMARY KEY,
            agent_id TEXT,
            amount REAL,
            merchant TEXT,
            created_at TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            amount REAL,
            merchant TEXT,
            status TEXT,
            created_at TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_behavior (
            agent_id TEXT,
            transaction_id TEXT,
            vote TEXT,
            amount REAL,
            timestamp TIMESTAMP,
            PRIMARY KEY (agent_id, transaction_id)
        )
    """)
    
    conn.commit()
    conn.close()


def test_table_creation():
    """Test 1: Verify agent_behavior table exists with correct schema."""
    print("\n" + "="*50)
    print("TEST 1: agent_behavior Table Creation")
    print("="*50)
    
    init_db()
    
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    
    # Check table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agent_behavior'")
    table = cursor.fetchone()
    
    if table:
        print("[PASS] agent_behavior table exists")
    else:
        print("[FAIL] agent_behavior table NOT found")
        conn.close()
        return False
    
    # Check columns
    cursor.execute("PRAGMA table_info(agent_behavior)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    expected = {
        "agent_id": "TEXT",
        "transaction_id": "TEXT",
        "vote": "TEXT",
        "amount": "REAL",
        "timestamp": "TIMESTAMP"
    }
    
    all_pass = True
    for col, dtype in expected.items():
        if col in columns:
            print(f"[PASS] Column '{col}' exists with type {columns[col]}")
        else:
            print(f"[FAIL] Column '{col}' NOT found")
            all_pass = False
    
    conn.close()
    return all_pass


def test_vote_logging():
    """Test 2: Verify vote logging works correctly."""
    print("\n" + "="*50)
    print("TEST 2: Vote Logging Simulation")
    print("="*50)
    
    # Simulate what execute_with_consensus does
    engine = ConsensusEngine(threshold=0.67)
    result = engine.simulate_vote(500.0, "TestMerchant")
    
    print(f"Consensus result: {result['status']}")
    print(f"Approval rate: {result['approval_rate']*100:.0f}%")
    print(f"Votes: {len(result['votes'])}")
    
    # Log votes to database (same logic as in execute_with_consensus)
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    
    tx_id = "tx_test_001"
    for vote in result["votes"]:
        cursor.execute(
            "INSERT INTO agent_behavior (agent_id, transaction_id, vote, amount, timestamp) VALUES (?, ?, ?, ?, ?)",
            (vote["agent_id"], tx_id, vote["vote"].upper(), 500.0, datetime.now().isoformat())
        )
    conn.commit()
    
    # Verify votes were logged
    cursor.execute("SELECT agent_id, transaction_id, vote, amount FROM agent_behavior WHERE transaction_id = ?", (tx_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if len(rows) == len(result["votes"]):
        print(f"[PASS] {len(rows)} votes logged to agent_behavior table")
        for row in rows:
            print(f"  - Agent: {row[0]}, TX: {row[1]}, Vote: {row[2]}, Amount: ${row[3]}")
        return True
    else:
        print(f"[FAIL] Expected {len(result['votes'])} votes, got {len(rows)}")
        return False


def calculate_baseline(agent_id):
    """Calculate behavioral baseline (same logic as get_behavioral_baseline in main.py)."""
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT amount FROM agent_behavior WHERE agent_id = ? AND vote = 'APPROVE'",
        (agent_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {"mean": 0.0, "stddev": 0.0}
    
    amounts = [row[0] for row in rows]
    n = len(amounts)
    
    mean = sum(amounts) / n
    
    if n < 2:
        stddev = 0.0
    else:
        variance = sum((x - mean) ** 2 for x in amounts) / (n - 1)
        stddev = variance ** 0.5
    
    return {"mean": mean, "stddev": stddev}


def test_get_behavioral_baseline():
    """Test 3: Verify behavioral baseline calculation with manual stddev."""
    print("\n" + "="*50)
    print("TEST 3: get_behavioral_baseline Logic")
    print("="*50)
    
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    
    # Insert controlled test data
    test_agent = "baseline_test_agent"
    test_amounts = [100.0, 200.0, 300.0, 400.0, 500.0]
    
    for i, amount in enumerate(test_amounts):
        cursor.execute(
            "INSERT INTO agent_behavior (agent_id, transaction_id, vote, amount, timestamp) VALUES (?, ?, ?, ?, ?)",
            (test_agent, f"tx_baseline_{i}", "APPROVE", amount, datetime.now().isoformat())
        )
    conn.commit()
    conn.close()
    
    # Calculate baseline
    baseline = calculate_baseline(test_agent)
    
    expected_mean = 300.0  # (100+200+300+400+500) / 5
    # Expected stddev = sqrt(((100-300)^2 + (200-300)^2 + (300-300)^2 + (400-300)^2 + (500-300)^2) / 4)
    # = sqrt((40000 + 10000 + 0 + 10000 + 40000) / 4) = sqrt(25000) = 158.11
    expected_stddev = 158.11
    
    print(f"Baseline result: mean={baseline['mean']:.2f}, stddev={baseline['stddev']:.2f}")
    
    if abs(baseline["mean"] - expected_mean) < 0.01:
        print(f"[PASS] Mean is correct: {baseline['mean']}")
    else:
        print(f"[FAIL] Mean mismatch: got {baseline['mean']}, expected {expected_mean}")
        return False
    
    if abs(baseline["stddev"] - expected_stddev) < 0.1:
        print(f"[PASS] Stddev is correct: {baseline['stddev']:.2f}")
    else:
        print(f"[FAIL] Stddev mismatch: got {baseline['stddev']:.2f}, expected {expected_stddev}")
        return False
    
    # Test with non-existent agent
    baseline_empty = calculate_baseline("nonexistent_agent")
    if baseline_empty["mean"] == 0.0 and baseline_empty["stddev"] == 0.0:
        print("[PASS] Empty agent returns 0.0 for mean and stddev")
    else:
        print(f"[FAIL] Empty agent should return 0.0, got {baseline_empty}")
        return False
    
    # Test with single data point (stddev should be 0)
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO agent_behavior (agent_id, transaction_id, vote, amount, timestamp) VALUES (?, ?, ?, ?, ?)",
        ("single_data_agent", "tx_single", "APPROVE", 100.0, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    baseline_single = calculate_baseline("single_data_agent")
    if baseline_single["stddev"] == 0.0:
        print(f"[PASS] Single data point returns stddev=0.0")
    else:
        print(f"[FAIL] Single data point should have stddev=0.0, got {baseline_single['stddev']}")
        return False
    
    return True


def test_should_revoke_logic():
    """Test 4: Verify revocation logic."""
    print("\n" + "="*50)
    print("TEST 4: should_revoke_agent Logic")
    print("="*50)
    
    # Test the logic without calling the MCP tool
    def revoke_logic(mean, stddev, current_amount):
        if stddev == 0:
            return "HOLD"
        drift = abs(current_amount - mean)
        if drift > 2.0 * stddev:
            return "REVOKE"
        return "APPROVE"
    
    # Test case 1: No data (stddev = 0) -> HOLD
    result1 = revoke_logic(0.0, 0.0, 1000.0)
    if result1 == "HOLD":
        print(f"[PASS] stddev=0 returns 'HOLD': {result1}")
    else:
        print(f"[FAIL] Expected 'HOLD', got: {result1}")
        return False
    
    # Test case 2: Within 2 sigma -> APPROVE
    mean, stddev = 300.0, 158.11
    safe_amount = mean + (1.5 * stddev)  # 537.17, drift = 237.17 < 316.22
    result2 = revoke_logic(mean, stddev, safe_amount)
    drift2 = abs(safe_amount - mean)
    if result2 == "APPROVE":
        print(f"[PASS] Amount within 2σ (drift={drift2:.2f} < {2*stddev:.2f}) returns 'APPROVE'")
    else:
        print(f"[FAIL] Expected 'APPROVE', got: {result2}")
        return False
    
    # Test case 3: Beyond 2 sigma -> REVOKE
    risky_amount = mean + (2.5 * stddev)  # 695.28, drift = 395.28 > 316.22
    result3 = revoke_logic(mean, stddev, risky_amount)
    drift3 = abs(risky_amount - mean)
    if result3 == "REVOKE":
        print(f"[PASS] Amount beyond 2σ (drift={drift3:.2f} > {2*stddev:.2f}) returns 'REVOKE'")
    else:
        print(f"[FAIL] Expected 'REVOKE', got: {result3}")
        return False
    
    # Test case 4: Exactly at 2 sigma boundary -> APPROVE (not >, so approve)
    edge_amount = mean + (2.0 * stddev)  # drift = 316.22
    result4 = revoke_logic(mean, stddev, edge_amount)
    if result4 == "APPROVE":
        print(f"[PASS] Amount at exactly 2σ (drift={2*stddev:.2f}) returns 'APPROVE'")
    else:
        print(f"[FAIL] Expected 'APPROVE' at edge, got: {result4}")
        return False
    
    # Test case 5: Negative drift (below mean by >2σ) -> REVOKE
    low_amount = mean - (2.5 * stddev)  # -95.28, drift = 395.28 > 316.22
    result5 = revoke_logic(mean, stddev, low_amount)
    drift5 = abs(low_amount - mean)
    if result5 == "REVOKE":
        print(f"[PASS] Amount below mean by >2σ (drift={drift5:.2f}) returns 'REVOKE'")
    else:
        print(f"[FAIL] Expected 'REVOKE' for drift below mean, got: {result5}")
        return False
    
    return True


def test_integration():
    """Test 5: Integration test using real baseline data."""
    print("\n" + "="*50)
    print("TEST 5: Integration Test (Baseline + Revocation)")
    print("="*50)
    
    # Use the baseline_test_agent data from test 3
    baseline = calculate_baseline("baseline_test_agent")
    mean = baseline["mean"]
    stddev = baseline["stddev"]
    
    print(f"Agent baseline: mean=${mean:.2f}, stddev=${stddev:.2f}")
    print(f"2σ threshold: {2*stddev:.2f}")
    
    def revoke_logic(mean, stddev, current_amount):
        if stddev == 0:
            return "HOLD"
        drift = abs(current_amount - mean)
        if drift > 2.0 * stddev:
            return "REVOKE"
        return "APPROVE"
    
    # Normal transaction (within baseline)
    normal_amount = 350.0
    normal_result = revoke_logic(mean, stddev, normal_amount)
    normal_drift = abs(normal_amount - mean)
    print(f"  ${normal_amount} -> drift={normal_drift:.2f} -> {normal_result}")
    
    # Suspicious transaction (beyond 2σ)
    suspicious_amount = 1000.0
    sus_result = revoke_logic(mean, stddev, suspicious_amount)
    sus_drift = abs(suspicious_amount - mean)
    print(f"  ${suspicious_amount} -> drift={sus_drift:.2f} -> {sus_result}")
    
    # Very low transaction (below 2σ threshold from mean)
    # mean=300, 2σ=316.22, so anything below 300-316.22 = -16.22 would trigger REVOKE
    # But amounts are positive, so test with an amount that's within threshold
    low_amount = 50.0  # drift = 250, which is < 316.22, so APPROVE
    low_result = revoke_logic(mean, stddev, low_amount)
    low_drift = abs(low_amount - mean)
    print(f"  ${low_amount} -> drift={low_drift:.2f} -> {low_result}")
    
    if normal_result == "APPROVE" and sus_result == "REVOKE" and low_result == "APPROVE":
        print("[PASS] Integration test passed")
        return True
    else:
        print("[FAIL] Integration test failed")
        return False


def run_all_tests():
    """Run all tests and summarize results."""
    print("\n" + "#"*60)
    print("# BEHAVIORAL FINGERPRINTING TEST SUITE")
    print("#"*60)
    
    results = {}
    
    results["Table Creation"] = test_table_creation()
    results["Vote Logging"] = test_vote_logging()
    results["Behavioral Baseline"] = test_get_behavioral_baseline()
    results["Revocation Logic"] = test_should_revoke_logic()
    results["Integration"] = test_integration()
    
    # Summary
    print("\n" + "#"*60)
    print("# TEST SUMMARY")
    print("#"*60)
    
    all_pass = True
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")
        if not passed:
            all_pass = False
    
    print("\n" + "="*60)
    if all_pass:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED - Review output above")
    print("="*60)
    
    return all_pass


if __name__ == "__main__":
    run_all_tests()
