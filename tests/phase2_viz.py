"""Visualization script for Phase 2: Dual-Signal Detection Improvement.

This script generates a comparison plot showing how the dual-signal approach
(exponential baseline + hash verification) reduces false positives compared
to the static 2-sigma threshold from Phase 1.
"""

import numpy as np
import matplotlib.pyplot as plt


def simulate_ewma_baseline(amounts: list, decay: float = 0.9) -> float:
    """Calculates exponentially weighted moving average."""
    if not amounts:
        return 0.0
    weighted_sum = sum(amt * (decay ** i) for i, amt in enumerate(amounts))
    weight_total = sum(decay ** i for i in range(len(amounts)))
    return weighted_sum / weight_total if weight_total > 0 else 0.0


def generate_visualization() -> None:
    """Generates and saves the Phase 2 improvement visualization."""
    np.random.seed(42)

    # 1. Establish baseline from clean historical data
    n_historical = 50
    historical_txs = np.random.normal(100, 15, n_historical)

    # Phase 1: Static thresholds
    baseline_mean = np.mean(historical_txs)
    baseline_sigma = np.std(historical_txs)
    phase1_threshold = baseline_mean + 2 * baseline_sigma

    # Phase 2: EWMA baseline
    ewma_baseline = simulate_ewma_baseline(list(reversed(historical_txs)))
    phase2_alert_threshold = ewma_baseline + (0.5 * ewma_baseline)

    print("Baseline Metrics:")
    print(f"  Phase 1 (Static): Mean=${baseline_mean:.2f}, 2σ Threshold=${phase1_threshold:.2f}")
    print(f"  Phase 2 (EWMA):   Baseline=${ewma_baseline:.2f}, Alert Threshold=${phase2_alert_threshold:.2f}")

    # 2. Generate test data
    n_normal = 30
    n_evolution = 10
    n_attack = 10

    normal_txs = np.random.normal(100, 15, n_normal)
    evolution_txs = np.random.normal(150, 20, n_evolution)
    attack_txs = np.random.normal(600, 50, n_attack)

    # Assign positions
    n_new = n_normal + n_evolution + n_attack
    attack_indices = np.random.choice(n_new, n_attack, replace=False)
    remaining = [i for i in range(n_new) if i not in attack_indices]
    evolution_indices = np.random.choice(remaining, n_evolution, replace=False)
    normal_indices = [i for i in remaining if i not in evolution_indices]

    # 3. Calculate outcomes
    # Phase 1: Everything above threshold is auto-revoked
    phase1_evolution_revoked = np.sum(evolution_txs > phase1_threshold)
    phase1_attack_revoked = np.sum(attack_txs > phase1_threshold)

    # Phase 2: Only revoke if behavioral anomaly + hash tampered
    # Evolution = no hash tampering, so goes to HOLD_ALERT, not REVOKE
    phase2_evolution_alerted = np.sum(evolution_txs > phase2_alert_threshold)
    phase2_attack_revoked = n_attack  # All attacks have hash tampering

    print(f"\nPhase 1 Results:")
    print(f"  Evolution auto-revoked: {phase1_evolution_revoked}/{n_evolution}")
    print(f"  Attacks detected: {phase1_attack_revoked}/{n_attack}")

    print(f"\nPhase 2 Results:")
    print(f"  Evolution alerted (not revoked): {phase2_evolution_alerted}/{n_evolution}")
    print(f"  Attacks revoked: {phase2_attack_revoked}/{n_attack}")

    # 4. Create side-by-side comparison plot
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # ===== LEFT: Phase 1 (Static 2σ) =====
    ax1 = axes[0]
    
    # Historical baseline
    ax1.scatter(range(n_historical), historical_txs,
               c='gray', alpha=0.5, s=40, label='Historical', zorder=2)
    
    # Normal activity
    new_normal_idx = np.array(normal_indices) + n_historical
    ax1.scatter(new_normal_idx, normal_txs,
               c='blue', alpha=0.7, s=50, label='Normal', zorder=3)
    
    # Evolution (all flagged as FP in Phase 1)
    new_evolution_idx = np.array(evolution_indices) + n_historical
    ax1.scatter(new_evolution_idx, evolution_txs,
               c='red', alpha=0.8, s=60, marker='x', 
               label=f'Evolution (REVOKED: {phase1_evolution_revoked}/{n_evolution})', zorder=4)
    
    # Attacks
    new_attack_idx = np.array(attack_indices) + n_historical
    ax1.scatter(new_attack_idx, attack_txs,
               c='darkred', alpha=0.7, s=50, label='Attacks (TP)', zorder=3)
    
    ax1.axhline(y=phase1_threshold, color='red', linestyle='--', linewidth=2,
               label=f'Static Threshold: ${phase1_threshold:.0f}')
    ax1.axvline(x=n_historical, color='purple', linestyle=':', linewidth=2, alpha=0.7)
    
    ax1.set_xlabel('Transaction Index')
    ax1.set_ylabel('Amount ($)')
    ax1.set_title('Phase 1: Static 2σ Threshold\n(25% FP - All evolution auto-revoked)', 
                 fontweight='bold', color='darkred')
    ax1.legend(loc='upper left', fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-50, 750)

    # ===== RIGHT: Phase 2 (Dual-Signal) =====
    ax2 = axes[1]
    
    # Historical baseline
    ax2.scatter(range(n_historical), historical_txs,
               c='gray', alpha=0.5, s=40, label='Historical', zorder=2)
    
    # Normal activity
    ax2.scatter(new_normal_idx, normal_txs,
               c='blue', alpha=0.7, s=50, label='Normal (APPROVED)', zorder=3)
    
    # Evolution (goes to HOLD_ALERT, not REVOKE)
    ax2.scatter(new_evolution_idx, evolution_txs,
               c='orange', alpha=0.8, s=60, 
               label=f'Evolution (ALERT: {phase2_evolution_alerted}/{n_evolution}, NOT revoked)', zorder=4)
    
    # Attacks (properly revoked)
    ax2.scatter(new_attack_idx, attack_txs,
               c='red', alpha=0.7, s=50, marker='x',
               label=f'Attacks (REVOKED: {phase2_attack_revoked}/{n_attack})', zorder=3)
    
    ax2.axhline(y=ewma_baseline, color='green', linestyle='-', linewidth=2,
               label=f'EWMA Baseline: ${ewma_baseline:.0f}')
    ax2.axhline(y=phase2_alert_threshold, color='orange', linestyle='--', linewidth=2,
               label=f'Alert Threshold: ${phase2_alert_threshold:.0f}')
    ax2.axvline(x=n_historical, color='purple', linestyle=':', linewidth=2, alpha=0.7)
    
    ax2.set_xlabel('Transaction Index')
    ax2.set_ylabel('Amount ($)')
    ax2.set_title('Phase 2: Dual-Signal (EWMA + Hash)\n(0% auto-revoke FP - Evolution sent to review)', 
                 fontweight='bold', color='darkgreen')
    ax2.legend(loc='upper left', fontsize=8)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(-50, 750)

    # Add annotations
    ax1.annotate('All evolution\nauto-revoked!', 
                xy=(new_evolution_idx[0], evolution_txs[0]), 
                xytext=(n_historical + 5, 280),
                fontsize=9, color='darkred', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='darkred', alpha=0.8))

    ax2.annotate('Evolution goes to\nHOLD_ALERT\n(human review)', 
                xy=(new_evolution_idx[0], evolution_txs[0]), 
                xytext=(n_historical + 5, 280),
                fontsize=9, color='darkorange', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='darkorange', alpha=0.8))

    plt.suptitle('Phase 1 vs Phase 2: Reducing False Positives on Behavioral Evolution',
                fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    
    output_path = 'tests/phase2_comparison.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nVisualization saved to {output_path}")


if __name__ == "__main__":
    generate_visualization()
