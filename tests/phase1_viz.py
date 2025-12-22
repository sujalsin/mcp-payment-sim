"""Visualization script for Phase 1: Static 2-Sigma Baseline Analysis.

This script generates a plot demonstrating the 'rigidity problem' of static
behavioral baselines, where legitimate behavioral evolution can trigger
false positive revocations.
"""

import numpy as np
import matplotlib.pyplot as plt


def generate_visualization() -> None:
    """Generates and saves the Phase 1 rigidity visualization."""
    # Set seed for deterministic output in analysis.
    np.random.seed(42)

    # 1. Establish a baseline from clean historical data.
    n_historical = 50
    historical_txs = np.random.normal(100, 15, n_historical)

    baseline_mean = np.mean(historical_txs)
    baseline_sigma = np.std(historical_txs)
    upper_threshold = baseline_mean + 2 * baseline_sigma
    lower_threshold = baseline_mean - 2 * baseline_sigma

    print("Baseline Metrics (Clean Historical Data):")
    print(f"  Mean: ${baseline_mean:.2f}")
    print(f"  Sigma: ${baseline_sigma:.2f}")
    print(f"  Upper Threshold (Mean + 2-Sigma): ${upper_threshold:.2f}")

    # 2. Generate test data including normal, evolution, and attack txs.
    n_new = 50
    n_normal = 30
    n_evolution = 10
    n_attack = 10

    normal_txs = np.random.normal(100, 15, n_normal)
    evolution_txs = np.random.normal(150, 20, n_evolution)
    attack_txs = np.random.normal(600, 50, n_attack)

    new_amounts = np.zeros(n_new)
    attack_indices = np.random.choice(n_new, n_attack, replace=False)
    remaining = [i for i in range(n_new) if i not in attack_indices]
    evolution_indices = np.random.choice(remaining, n_evolution, replace=False)
    normal_indices = [i for i in remaining if i not in evolution_indices]

    new_amounts[normal_indices] = normal_txs
    new_amounts[evolution_indices] = evolution_txs
    new_amounts[attack_indices] = attack_txs

    # 3. Calculate performance metrics.
    evolution_breaches = np.sum(evolution_txs > upper_threshold)
    attack_breaches = np.sum(attack_txs > upper_threshold)
    fp_rate = (evolution_breaches / (n_normal + n_evolution)) * 100

    print("\nTest Results (New Transactions):")
    print(f"  Evolution Breaches (False Positives): {evolution_breaches}/{n_evolution}")
    print(f"  Attack Breaches (True Positives): {attack_breaches}/{n_attack}")
    print(f"  Calculated False Positive Rate: {fp_rate:.1f}%")

    # 4. Generate the plot.
    fig, ax = plt.subplots(figsize=(14, 7))

    # Plot baseline period.
    ax.scatter(range(n_historical), historical_txs, 
               c='gray', alpha=0.5, s=40, label='Historical Baseline', zorder=2)

    # Plot normal activity.
    new_normal_idx = np.array(normal_indices) + n_historical
    ax.scatter(new_normal_idx, normal_txs, 
               c='blue', alpha=0.7, s=50, label='Normal Activity', zorder=3)

    # Plot behavioral evolution (Potential false positives).
    new_evolution_idx = np.array(evolution_indices) + n_historical
    ax.scatter(new_evolution_idx, evolution_txs, 
               c='orange', alpha=0.8, s=60, label='Behavioral Evolution (FP)', zorder=4)

    # Plot simulated attacks.
    new_attack_idx = np.array(attack_indices) + n_historical
    ax.scatter(new_attack_idx, attack_txs, 
               c='red', alpha=0.7, s=50, label='Simulated Attacks (TP)', zorder=3)

    # Threshold markers.
    ax.axhline(y=baseline_mean, color='black', linestyle='-', linewidth=2, 
               label=f'Baseline Mean: ${baseline_mean:.0f}')
    ax.axhline(y=upper_threshold, color='red', linestyle='--', linewidth=2,
               label=f'Upper Threshold (2-Sigma): ${upper_threshold:.0f}')

    ax.axvline(x=n_historical, color='purple', linestyle=':', linewidth=2, alpha=0.7)
    ax.text(n_historical + 1, 50, 'Baseline Conclusion', fontsize=9, color='purple')

    ax.set_xlabel('Transaction Index')
    ax.set_ylabel('Amount ($)')
    ax.set_title(f'Analysis: Static 2-Sigma Baseline Performance (FP Rate: {fp_rate:.1f}%)', 
                 fontweight='bold')

    ax.legend(loc='upper left', fontsize=9, framealpha=0.9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(-50, 750)

    # Annotations.
    ax.annotate('False Positive Cluster\n(Evolution incorrectly flagged)', 
                xy=(new_evolution_idx[0], evolution_txs[0]), 
                xytext=(n_historical + 5, 280),
                fontsize=10, color='darkorange', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='darkorange', alpha=0.8))

    plt.tight_layout()
    output_path = 'tests/phase1_rigidity.png'
    plt.savefig(output_path, dpi=150)
    print(f"\nVisualization saved to {output_path}")


if __name__ == "__main__":
    generate_visualization()
