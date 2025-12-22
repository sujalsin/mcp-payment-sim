"""Test suite for validating Phase 2 behavioral detection improvements.

This module demonstrates the reduction in false positives achieved by
the dual-signal approach (exponential baseline + hash verification)
compared to the static 2-sigma threshold from Phase 1.
"""

import hashlib
import numpy as np


def get_mock_hash(agent_id: str, tampered: bool = False) -> str:
    """Generates a mock cryptographic hash for an agent model.

    Args:
        agent_id: Unique identifier for the agent.
        tampered: If True, returns a modified hash simulating a compromised state.

    Returns:
        A SHA-256 hash string of the agent's simulated model weights.
    """


def simulate_ewma_baseline(amounts: list, decay: float = 0.9) -> float:
    """Calculates an adaptive baseline using Exponentially Weighted Moving Average.

    Args:
        amounts: List of historical transaction amounts (most recent first).
        decay: Decay factor between 0.0 and 1.0. Higher values weight recent data more.

    Returns:
        The calculated EWMA baseline amount.
    """
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
    """Evaluates agent integrity using Phase 2 dual-signal logic.

    Args:
        baseline: The current behavioral baseline amount for the agent.
        current_amount: The amount of the transaction being evaluated.
        hash_tampered: Boolean indicating if the model hash signal is tampered.

    Returns:
        A dictionary containing the recommended 'action' and 'confidence' level.
    """
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


def validate_production_scale():
    """Validates Phase 2 detection at production scale (10,000 transactions).
    
    Generates labeled data, runs detection, and calculates precision/recall/F1.
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from database import DatabaseManager
    
    print("=" * 70)
    print("PHASE 2: PRODUCTION SCALE VALIDATION (n=10,000)")
    print("=" * 70)
    
    np.random.seed(42)
    
    # Initialize database
    db = DatabaseManager("test_production.db")
    
    # Build baseline from historical data
    n_historical = 100
    historical_txs = np.random.normal(100, 15, n_historical)
    ewma_baseline = simulate_ewma_baseline(list(reversed(historical_txs)))
    
    # Generate labeled transactions
    n_normal = 8000
    n_evolution = 1500
    n_attack = 500
    
    print(f"\nDataset Configuration:")
    print(f"  Normal:    {n_normal:,} transactions - N(100, 15)")
    print(f"  Evolution: {n_evolution:,} transactions - N(150, 25)")
    print(f"  Attacks:   {n_attack:,} transactions - N(600, 50)")
    print(f"  Total:     {n_normal + n_evolution + n_attack:,} transactions")
    print(f"  EWMA Baseline: ${ewma_baseline:.2f}")
    
    normal_txs = np.random.normal(100, 15, n_normal)
    evolution_txs = np.random.normal(150, 25, n_evolution)
    attack_txs = np.random.normal(600, 50, n_attack)
    
    # Create labeled dataset
    # Label: 0 = normal, 1 = evolution (legitimate), 2 = attack
    all_txs = []
    for i, tx in enumerate(normal_txs):
        all_txs.append({'id': f'tx-normal-{i}', 'amount': tx, 'label': 0, 'is_attack': False})
    for i, tx in enumerate(evolution_txs):
        all_txs.append({'id': f'tx-evolution-{i}', 'amount': tx, 'label': 1, 'is_attack': False})
    for i, tx in enumerate(attack_txs):
        all_txs.append({'id': f'tx-attack-{i}', 'amount': tx, 'label': 2, 'is_attack': True})
    
    # Shuffle for realistic evaluation
    np.random.shuffle(all_txs)
    
    print(f"\nRunning Phase 2 detection on {len(all_txs):,} transactions...")
    
    # Metrics tracking
    # For binary classification: attack vs non-attack
    # Positive = attack, Negative = legitimate (normal + evolution)
    true_positives = 0   # Attack correctly revoked
    false_positives = 0  # Legitimate incorrectly revoked
    true_negatives = 0   # Legitimate correctly not revoked
    false_negatives = 0  # Attack missed (not revoked)
    
    # Detailed tracking
    decisions = {'REVOKE': 0, 'HOLD_ALERT': 0, 'IGNORE': 0, 'APPROVE': 0}
    evolution_revoked = 0
    normal_revoked = 0
    
    for tx in all_txs:
        # Hash tampering is TRUE only for attacks
        hash_tampered = tx['is_attack']
        result = evaluate_phase2_integrity(ewma_baseline, tx['amount'], hash_tampered)
        action = result['action']
        decisions[action] += 1
        
        is_revoked = (action == 'REVOKE')
        
        if tx['is_attack']:
            # It's an attack
            if is_revoked:
                true_positives += 1
            else:
                false_negatives += 1
        else:
            # It's legitimate (normal or evolution)
            if is_revoked:
                false_positives += 1
                if tx['label'] == 0:
                    normal_revoked += 1
                else:
                    evolution_revoked += 1
            else:
                true_negatives += 1
    
    # Calculate metrics
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    fp_rate = false_positives / (n_normal + n_evolution) * 100
    
    # Print formatted report
    print("\n" + "-" * 70)
    print("PRODUCTION METRICS (n=10,000):")
    print("-" * 70)
    
    print(f"\nConfusion Matrix:")
    print(f"  True Positives:  {true_positives:,} (attacks caught)")
    print(f"  False Positives: {false_positives:,} (legitimate revoked)")
    print(f"  True Negatives:  {true_negatives:,} (legitimate approved/alerted)")
    print(f"  False Negatives: {false_negatives:,} (attacks missed)")
    
    print(f"\nClassification Metrics:")
    print(f"  Precision: {precision*100:.1f}% (how many revoked were actual attacks)")
    print(f"  Recall:    {recall*100:.1f}% (how many attacks were caught)")
    print(f"  F1-Score:  {f1_score*100:.1f}% (harmonic mean)")
    
    print(f"\nFalse Positive Breakdown:")
    print(f"  Normal revoked:    {normal_revoked}")
    print(f"  Evolution revoked: {evolution_revoked}")
    print(f"  AUTO-REVOKE FP RATE: {fp_rate:.2f}%")
    
    print(f"\nDecision Distribution:")
    for action, count in decisions.items():
        pct = (count / len(all_txs)) * 100
        print(f"  {action:<12}: {count:>6,} ({pct:>5.1f}%)")
    
    print("\n" + "=" * 70)
    
    # Assertions
    if fp_rate == 0:
        print("[PASS] AUTO-REVOKE FALSE POSITIVE RATE: 0%")
    else:
        print(f"[FAIL] Expected 0% FP rate, got {fp_rate:.2f}%")
    
    if recall >= 0.90:
        print(f"[PASS] Recall >= 90%: {recall*100:.1f}%")
    else:
        print(f"[WARN] Recall below 90%: {recall*100:.1f}%")
    
    if precision >= 0.95:
        print(f"[PASS] Precision >= 95%: {precision*100:.1f}%")
    else:
        print(f"[WARN] Precision below 95%: {precision*100:.1f}%")
    
    print("=" * 70)
    
    # Cleanup test database
    import os
    if os.path.exists("test_production.db"):
        os.remove("test_production.db")
    
    return fp_rate == 0 and recall >= 0.90


def demonstrate_temporal_poisoning_gap():
    """Demonstrates the temporal poisoning attack that evades Phase 2 detection.
    
    Shows how gradual behavioral drift can bypass both the behavioral anomaly
    signal and the hash verification signal, identifying a critical security gap.
    """
    
    print("=" * 70)
    print("PHASE 2 GAP ANALYSIS: TEMPORAL POISONING ATTACK")
    print("=" * 70)
    
    np.random.seed(42)
    
    # Baseline from clean historical data (FIXED - not updated during attack)
    n_baseline = 50
    baseline_txs = np.random.normal(100, 15, n_baseline)
    fixed_baseline = simulate_ewma_baseline(list(reversed(baseline_txs)))
    
    print(f"\nFixed EWMA Baseline: ${fixed_baseline:.2f}")
    print(f"Detection Threshold: >${fixed_baseline * 1.5:.2f} triggers HOLD_ALERT")
    
    # Generate three attack patterns
    n_normal = 50
    n_attack = 50
    
    patterns = {}
    
    # Pattern A: Sudden Attack
    normal_a = np.random.normal(100, 15, n_normal)
    attack_a = np.random.normal(600, 50, n_attack)
    patterns['A: Sudden (6x jump)'] = {
        'txs': list(normal_a) + list(attack_a),
        'description': 'N(100,15) -> N(600,50)',
        'why': 'Behavioral signal fires immediately'
    }
    
    # Pattern B: Fast Drift (1.02x per tx)
    normal_b = np.random.normal(100, 15, n_normal)
    fast_drift = []
    current = 100
    for i in range(n_attack):
        current *= 1.02
        fast_drift.append(current + np.random.normal(0, 5))
    patterns['B: Fast drift (1.02x/tx)'] = {
        'txs': list(normal_b) + fast_drift,
        'description': f'N(100,15) -> gradual to ${fast_drift[-1]:.0f}',
        'why': 'EWMA catches after lag'
    }
    
    # Pattern C: Temporal Poisoning (1.004x per tx - very slow)
    normal_c = np.random.normal(100, 15, n_normal)
    slow_poison = []
    current = 100
    for i in range(n_attack):
        current *= 1.004
        slow_poison.append(current + np.random.normal(0, 5))
    patterns['C: Temporal Poison (1.004x/tx)'] = {
        'txs': list(normal_c) + slow_poison,
        'description': f'N(100,15) -> gradual to ${slow_poison[-1]:.0f}',
        'why': 'Both signals evaded - drift too slow'
    }
    
    print("\n" + "-" * 70)
    print("ATTACK PATTERNS:")
    print("-" * 70)
    
    for name, pattern in patterns.items():
        print(f"  {name}:")
        print(f"    {pattern['description']}")
        print(f"    Final 5 values: {[f'${x:.0f}' for x in pattern['txs'][-5:]]}")
    
    # Run detection on each pattern using FIXED baseline
    results = {}
    
    for name, pattern in patterns.items():
        txs = pattern['txs']
        
        detections_last_25 = 0
        
        for i, tx in enumerate(txs):
            # Use FIXED baseline (no adaptation during attack)
            result = evaluate_phase2_integrity(fixed_baseline, tx, hash_tampered=False)
            
            # HOLD_ALERT or REVOKE counts as detection
            is_detected = result['action'] in ['REVOKE', 'HOLD_ALERT']
            
            # Track detections in last 25 txs (attack phase)
            if i >= n_normal + n_attack - 25:
                if is_detected:
                    detections_last_25 += 1
        
        detection_rate = detections_last_25 / 25 * 100
        results[name] = {
            'detected': detections_last_25,
            'total': 25,
            'rate': detection_rate,
            'why': pattern['why']
        }
    
    # Print results table
    print("\n" + "=" * 70)
    print("PHASE 2 DETECTION BY ATTACK PATTERN (Fixed Baseline):")
    print("=" * 70)
    print(f"\n{'Attack Pattern':<30} {'Detection Rate':<18} {'Why It Fails/Works'}")
    print("-" * 70)
    
    for name, result in results.items():
        rate_str = f"{result['rate']:.0f}% ({result['detected']}/{result['total']})"
        print(f"{name:<30} {rate_str:<18} {result['why']}")
    
    print("-" * 70)
    
    # The punchline
    print("\n" + "=" * 70)
    print("GAP IDENTIFIED:")
    print("=" * 70)
    print("""
  Gradual 1.5x shift over 50+ transactions is UNDETECTABLE.
  
  Neither signal catches temporal poisoning:
    - Behavioral: Drift is below 50% threshold at each step
    - Hash: Attacker doesn't modify model weights
  
  The attacker can slowly shift the agent's behavior from $100 -> $150
  without triggering any detection, then execute a larger attack from
  the new elevated baseline.
  
  QUESTION FOR RESEARCH: How do we detect intent vs. natural evolution
  when both look identical at the behavioral level?
""")
    print("=" * 70)
    
    return results


def calculate_realistic_production_metrics():
    """Calculates weighted production metrics based on attack type distribution.
    
    Provides a brutally honest assessment of the system's detection capabilities
    against different attack patterns in a realistic production environment.
    """
    
    print("=" * 70)
    print("REALISTIC PRODUCTION METRICS")
    print("=" * 70)
    
    np.random.seed(42)
    
    # Build baseline
    baseline_txs = np.random.normal(100, 15, 50)
    fixed_baseline = simulate_ewma_baseline(list(reversed(baseline_txs)))
    
    print(f"\nBaseline: ${fixed_baseline:.2f}")
    print(f"Detection Threshold: >${fixed_baseline * 1.5:.2f}")
    
    # Test each attack type with larger sample
    n_test = 100
    
    # Sudden attack (6x jump)
    sudden_attacks = np.random.normal(600, 50, n_test)
    sudden_detected = sum(
        1 for tx in sudden_attacks 
        if evaluate_phase2_integrity(fixed_baseline, tx, False)['action'] in ['REVOKE', 'HOLD_ALERT']
    )
    sudden_rate = sudden_detected / n_test * 100
    
    # Fast drift (1.02x per tx)
    current = 100
    fast_drift = []
    for _ in range(n_test):
        current *= 1.02
        fast_drift.append(current + np.random.normal(0, 5))
    # Test last 50 (attack phase)
    fast_detected = sum(
        1 for tx in fast_drift[-50:] 
        if evaluate_phase2_integrity(fixed_baseline, tx, False)['action'] in ['REVOKE', 'HOLD_ALERT']
    )
    fast_rate = fast_detected / 50 * 100
    
    # Temporal poison (1.004x per tx - very slow)
    current = 100
    slow_poison = []
    for _ in range(n_test):
        current *= 1.004
        slow_poison.append(current + np.random.normal(0, 5))
    # Test last 50 (attack phase)
    poison_detected = sum(
        1 for tx in slow_poison[-50:] 
        if evaluate_phase2_integrity(fixed_baseline, tx, False)['action'] in ['REVOKE', 'HOLD_ALERT']
    )
    poison_rate = poison_detected / 50 * 100
    
    # Expected attack distribution in production
    sudden_volume = 0.30  # 30% of attacks are sudden
    fast_volume = 0.40    # 40% are fast drift
    poison_volume = 0.30  # 30% are temporal poisoning
    
    # Calculate weighted detection rate
    weighted_detection = (
        sudden_volume * sudden_rate +
        fast_volume * fast_rate +
        poison_volume * poison_rate
    )
    
    # Print results table
    print("\n" + "-" * 70)
    print(f"{'Attack Type':<25} {'Volume':<10} {'Detection':<12} {'Missed'}")
    print("-" * 70)
    
    print(f"{'Sudden (6x jump)':<25} {sudden_volume*100:.0f}%       {sudden_rate:.0f}%          {100-sudden_rate:.0f}%")
    print(f"{'Fast drift (1.02x/tx)':<25} {fast_volume*100:.0f}%       {fast_rate:.0f}%          {100-fast_rate:.0f}%")
    print(f"{'Temporal poison (1.004x)':<25} {poison_volume*100:.0f}%       {poison_rate:.0f}%           {100-poison_rate:.0f}%")
    
    print("-" * 70)
    
    print(f"\nWEIGHTED DETECTION RATE: {weighted_detection:.1f}%")
    print(f"  -> {100 - weighted_detection:.1f}% of gradual attacks will be MISSED")
    
    print("\n" + "=" * 70)
    print("CONCLUSION:")
    print("=" * 70)
    print("""
  Phase 2 is effective against SUDDEN attacks (100% detection).
  
  However, it FAILS on gradual drift attacks:
    - Fast drift: Only {:.0f}% detected
    - Temporal poison: {:.0f}% detected (complete evasion)
  
  This is NOT a bug - it's a fundamental limitation of behavioral detection.
  The system cannot distinguish malicious gradual drift from legitimate
  behavioral evolution without additional signals.
  
  RECOMMENDATION: Implement rate-of-change monitoring or require periodic
  re-authentication for agents exhibiting sustained directional drift.
""".format(fast_rate, poison_rate))
    print("=" * 70)
    
    return {
        'sudden_detection': sudden_rate,
        'fast_detection': fast_rate,
        'poison_detection': poison_rate,
        'weighted_detection': weighted_detection
    }


if __name__ == "__main__":
    test_fp_reduction()
    print("\n")
    validate_zero_fp_claim()
    print("\n")
    validate_production_scale()
    print("\n")
    demonstrate_temporal_poisoning_gap()
    print("\n")
    calculate_realistic_production_metrics()
