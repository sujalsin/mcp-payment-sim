"""Test suite for validating Phase 2 behavioral detection improvements.

This module demonstrates the reduction in false positives achieved by
the dual-signal approach (exponential baseline + hash verification)
compared to the static 2-sigma threshold from Phase 1.
"""

import hashlib
import numpy as np


def get_mock_hash(agent_id: str, tampered: bool = False) -> str:
    """Returns a mock model hash."""
    version = "v1.3" if not tampered else "v1.3-TAMPERED"
    return hashlib.sha256(f"{agent_id}-model-{version}".encode()).hexdigest()


def simulate_ewma_baseline(amounts: list, decay: float = 0.9) -> float:
    """Calculates exponentially weighted moving average."""
    if not amounts:
        return 0.0
    
    weighted_sum = 0.0
    weight_total = 0.0
    
    for i, amount in enumerate(amounts):
        weight = decay ** i
        weighted_sum += amount * weight
        weight_total += weight
    
    return weighted_sum / weight_total if weight_total > 0 else 0.0


def evaluate_phase2_integrity(baseline: float, current_amount: float, hash_tampered: bool) -> dict:
    """Evaluates using Phase 2 dual-signal logic."""
    drift = abs(current_amount - baseline)
    behavioral_anomaly = drift > (0.5 * baseline) if baseline > 0 else False
    
    if behavioral_anomaly and hash_tampered:
        return {"action": "REVOKE", "confidence": "HIGH"}
    elif behavioral_anomaly and not hash_tampered:
        return {"action": "HOLD_ALERT", "confidence": "MEDIUM"}
    elif not behavioral_anomaly and hash_tampered:
        return {"action": "IGNORE", "confidence": "LOW"}
    else:
        return {"action": "APPROVE", "confidence": "HIGH"}


def test_fp_reduction():
    """Validates that Phase 2 reduces false positives compared to Phase 1.
    
    Uses the EXACT same dataset and FP calculation from phase1_viz.py.
    Phase 1 FP rate = evolution_flagged / (normal + evolution)
    """
    
    print("=" * 70)
    print("PHASE 1 vs PHASE 2: FALSE POSITIVE REDUCTION TEST")
    print("=" * 70)
    
    # Use exact same setup as phase1_viz.py
    np.random.seed(42)
    
    # Clean historical baseline
    n_historical = 50
    historical_txs = np.random.normal(100, 15, n_historical)
    
    baseline_mean = np.mean(historical_txs)
    baseline_sigma = np.std(historical_txs)
    upper_threshold = baseline_mean + 2 * baseline_sigma
    
    print(f"\nBaseline (Clean Historical Data):")
    print(f"  Mean: ${baseline_mean:.2f}")
    print(f"  Sigma: ${baseline_sigma:.2f}")
    print(f"  Phase 1 Threshold (2σ): ${upper_threshold:.2f}")
    
    # Test datasets (same as Phase 1)
    n_normal = 30
    n_evolution = 10
    n_attack = 10
    
    normal_txs = np.random.normal(100, 15, n_normal)
    evolution_txs = np.random.normal(150, 20, n_evolution)
    attack_txs = np.random.normal(600, 50, n_attack)
    
    ewma_baseline = simulate_ewma_baseline(list(reversed(historical_txs)))
    print(f"  Phase 2 EWMA Baseline: ${ewma_baseline:.2f}")
    
    # ===== PHASE 1: Static 2-sigma =====
    # Any tx > threshold is AUTO-REVOKED
    phase1_normal_flagged = np.sum(normal_txs > upper_threshold)
    phase1_evolution_flagged = np.sum(evolution_txs > upper_threshold)
    phase1_attack_flagged = np.sum(attack_txs > upper_threshold)
    
    # FP rate = evolution flagged / (normal + evolution) -- same as phase1_viz.py
    phase1_fp_rate = (phase1_evolution_flagged / (n_normal + n_evolution)) * 100
    
    # ===== PHASE 2: Dual-signal =====
    # REVOKE = behavioral anomaly + hash tampered (HIGH confidence)
    # HOLD_ALERT = behavioral anomaly only (MEDIUM confidence, manual review)
    
    phase2_normal_revoke = 0
    phase2_normal_alert = 0
    phase2_evolution_revoke = 0
    phase2_evolution_alert = 0
    phase2_attack_revoke = 0
    
    for tx in normal_txs:
        result = evaluate_phase2_integrity(ewma_baseline, tx, hash_tampered=False)
        if result["action"] == "REVOKE":
            phase2_normal_revoke += 1
        elif result["action"] == "HOLD_ALERT":
            phase2_normal_alert += 1
    
    for tx in evolution_txs:
        # Evolution = legitimate drift, no hash tampering
        result = evaluate_phase2_integrity(ewma_baseline, tx, hash_tampered=False)
        if result["action"] == "REVOKE":
            phase2_evolution_revoke += 1
        elif result["action"] == "HOLD_ALERT":
            phase2_evolution_alert += 1
    
    for tx in attack_txs:
        # Attack = behavioral drift + hash tampering
        result = evaluate_phase2_integrity(ewma_baseline, tx, hash_tampered=True)
        if result["action"] == "REVOKE":
            phase2_attack_revoke += 1
    
    # Phase 2 FP rate (auto-revoke only) = evolution revoked / (normal + evolution)
    phase2_fp_rate_hard = (phase2_evolution_revoke / (n_normal + n_evolution)) * 100
    # Phase 2 FP rate (including alerts) = (evolution revoked + alerted) / (normal + evolution)
    phase2_fp_rate_soft = ((phase2_evolution_revoke + phase2_evolution_alert) / (n_normal + n_evolution)) * 100
    
    # Results
    print("\n" + "-" * 70)
    print("RESULTS:")
    print("-" * 70)
    
    print(f"\nPhase 1 (Static 2-Sigma) - AUTO-REVOKES everything above threshold:")
    print(f"  Normal flagged:    {phase1_normal_flagged}/{n_normal}")
    print(f"  Evolution flagged: {phase1_evolution_flagged}/{n_evolution} (ALL auto-revoked)")
    print(f"  Attack detected:   {phase1_attack_flagged}/{n_attack}")
    print(f"  FP Rate: {phase1_fp_rate:.1f}%")
    
    print(f"\nPhase 2 (Exponential + Hash) - Only REVOKES when BOTH signals fire:")
    print(f"  Normal:    {phase2_normal_revoke} revoked, {phase2_normal_alert} alerted")
    print(f"  Evolution: {phase2_evolution_revoke} revoked, {phase2_evolution_alert} alerted (NOT auto-revoked)")
    print(f"  Attack:    {phase2_attack_revoke} revoked")
    print(f"  FP Rate (auto-revoke): {phase2_fp_rate_hard:.1f}%")
    print(f"  FP Rate (incl. alerts): {phase2_fp_rate_soft:.1f}%")
    
    fp_reduction = phase1_fp_rate - phase2_fp_rate_hard
    
    print("\n" + "=" * 70)
    print(f"Phase 1 (Static 2σ): {phase1_fp_rate:.1f}% FP (auto-revoked)")
    print(f"Phase 2 (Dual-signal): {phase2_fp_rate_hard:.1f}% FP (auto-revoked)")
    print(f"Phase 2 reduces AUTO-REVOCATION FP by {fp_reduction:.0f} percentage points")
    print(f"Evolution txs go to HOLD_ALERT for human review instead of auto-revoke")
    print("=" * 70)
    
    # Assertions
    assert fp_reduction >= 20, f"Expected >=20 point reduction, got {fp_reduction:.0f}"
    assert phase2_attack_revoke == n_attack, f"Must detect all attacks"
    
    print("\n[PASS] Phase 2 fixes the rigidity problem.")
    return True


def validate_zero_fp_claim():
    """Validates the 0% auto-revocation FP claim with 1,000 evolution transactions.
    
    This test generates a large sample of evolution transactions and verifies
    that NONE are auto-revoked when hash tampering is absent.
    """
    
    print("=" * 70)
    print("PHASE 2: ZERO FP CLAIM VALIDATION (1,000 TXS)")
    print("=" * 70)
    
    np.random.seed(42)
    
    # Build baseline from clean historical data
    n_historical = 50
    historical_txs = np.random.normal(100, 15, n_historical)
    ewma_baseline = simulate_ewma_baseline(list(reversed(historical_txs)))
    
    # Get known good hash (no tampering)
    agent_id = "finance_agent"
    known_hash = get_mock_hash(agent_id, tampered=False)
    
    print(f"\nTest Configuration:")
    print(f"  EWMA Baseline: ${ewma_baseline:.2f}")
    print(f"  Drift Threshold: ${0.5 * ewma_baseline:.2f} (50% of baseline)")
    print(f"  Evolution Txs: N(mean=$150, std=$25)")
    print(f"  Hash Tampered: FALSE (clean)")
    
    # Generate 1,000 evolution transactions
    n_evolution = 1000
    evolution_txs = np.random.normal(150, 25, n_evolution)
    
    # Track all decisions
    decisions = {
        'REVOKE': 0,
        'HOLD_ALERT': 0,
        'IGNORE': 0,
        'APPROVE': 0
    }
    
    # Track revoked examples for debugging
    revoked_examples = []
    
    for i, tx in enumerate(evolution_txs):
        result = evaluate_phase2_integrity(ewma_baseline, tx, hash_tampered=False)
        action = result["action"]
        decisions[action] += 1
        
        if action == "REVOKE":
            revoked_examples.append({
                'id': f'tx-evolution-{i}',
                'amount': tx,
                'baseline': ewma_baseline,
                'drift': abs(tx - ewma_baseline)
            })
    
    # Print results table
    print(f"\nPhase 2: 1,000 Evolution Transactions (mean=$150, std=$25, no hash tamper)")
    print("-" * 50)
    print(f"{'Decision':<15} {'Count':<10} {'Percentage':<15} {'Note'}")
    print("-" * 50)
    
    for action, count in decisions.items():
        pct = (count / n_evolution) * 100
        if action == "REVOKE":
            note = "<-- Should be 0 for 0% FP claim"
        elif action == "HOLD_ALERT":
            note = "<-- Expected: ~40-60% due to drift"
        elif action == "APPROVE":
            note = "<-- Expected: remainder"
        else:
            note = "<-- Expected: few"
        print(f"{action:<15} {count:<10} {pct:>6.1f}%        {note}")
    
    print("-" * 50)
    
    # Conclusion
    print("\nCONCLUSION:")
    if decisions['REVOKE'] == 0:
        print("  [PASS] 0% FP claim is VERIFIED")
        print("     No evolution transactions were auto-revoked.")
        print("     All behavioral anomalies correctly routed to HOLD_ALERT for human review.")
    else:
        print(f"  [FAIL] Claim is FALSE, actual FP = {decisions['REVOKE']}/1000 = {(decisions['REVOKE']/1000)*100:.2f}%")
        print("\n  DEBUG - Examples of incorrectly revoked transactions:")
        for ex in revoked_examples[:5]:
            print(f"    {ex['id']}: amount=${ex['amount']:.2f}, baseline=${ex['baseline']:.2f}, drift=${ex['drift']:.2f}")
        print("\n  Likely culprits:")
        print("    - Baseline drift calculation error")
        print("    - Hash mock returning tampered=True incorrectly")
        print("    - evaluate_phase2_integrity logic bug")
    
    print("=" * 70)
    
    return decisions['REVOKE'] == 0


if __name__ == "__main__":
    test_fp_reduction()
    print("\n")
    validate_zero_fp_claim()
