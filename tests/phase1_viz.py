"""
Phase 1 Visualization: Why the naive 2σ static baseline fails.

REALISTIC SCENARIO:
1. Calculate threshold on CLEAN historical data only
2. Then introduce attacks + legitimate behavioral evolution
3. Show that both breach the threshold - causing false positives
"""
import numpy as np
import matplotlib.pyplot as plt

# Set seed for reproducibility
np.random.seed(42)

# =============================================
# PHASE 1: Build baseline on CLEAN historical data
# =============================================
n_historical = 50  # Clean historical transactions
historical_txs = np.random.normal(100, 15, n_historical)

# Calculate baseline from CLEAN data only
baseline_mean = np.mean(historical_txs)
baseline_std = np.std(historical_txs)
upper_threshold = baseline_mean + 2 * baseline_std
lower_threshold = baseline_mean - 2 * baseline_std

print("=" * 50)
print("BASELINE (from clean historical data)")
print("=" * 50)
print(f"  Mean: ${baseline_mean:.2f}")
print(f"  StdDev: ${baseline_std:.2f}")
print(f"  Upper threshold (mean+2σ): ${upper_threshold:.2f}")
print(f"  Lower threshold (mean-2σ): ${lower_threshold:.2f}")

# =============================================
# PHASE 2: New transactions (mix of normal, evolution, attacks)
# =============================================
n_new = 50

# 30 normal transactions (same distribution as historical)
n_normal = 30
normal_txs = np.random.normal(100, 15, n_normal)

# 10 legitimate behavioral evolution (gradually higher amounts)
n_evolution = 10
evolution_txs = np.random.normal(150, 20, n_evolution)  # Agent adapted to new patterns

# 10 attack transactions
n_attack = 10
attack_txs = np.random.normal(600, 50, n_attack)

# Create timeline for new transactions
new_amounts = np.zeros(n_new)
tx_types = np.zeros(n_new, dtype=int)  # 0=normal, 1=evolution, 2=attack

# Scatter them throughout the timeline
attack_indices = np.random.choice(n_new, n_attack, replace=False)
remaining = [i for i in range(n_new) if i not in attack_indices]
evolution_indices = np.random.choice(remaining, n_evolution, replace=False)
normal_indices = [i for i in remaining if i not in evolution_indices]

new_amounts[normal_indices] = normal_txs
new_amounts[evolution_indices] = evolution_txs
new_amounts[attack_indices] = attack_txs
tx_types[attack_indices] = 2
tx_types[evolution_indices] = 1

# =============================================
# Calculate FP/TP rates
# =============================================
normal_breaches = np.sum(normal_txs > upper_threshold)
evolution_breaches = np.sum(evolution_txs > upper_threshold)
attack_breaches = np.sum(attack_txs > upper_threshold)

# False positives = evolution txs flagged (they're legitimate!)
# True positives = attack txs flagged
fp_count = evolution_breaches
tp_count = attack_breaches
fn_count = n_attack - attack_breaches
tn_count = n_normal + n_evolution - evolution_breaches - normal_breaches

fp_rate = (fp_count / (n_normal + n_evolution)) * 100  # FP rate among legitimate txs

print("\n" + "=" * 50)
print("RESULTS (applying baseline to new transactions)")
print("=" * 50)
print(f"  Normal txs breaching threshold: {normal_breaches}/{n_normal}")
print(f"  Evolution txs breaching threshold: {evolution_breaches}/{n_evolution} (FALSE POSITIVES)")
print(f"  Attack txs breaching threshold: {attack_breaches}/{n_attack} (TRUE POSITIVES)")
print(f"\n  FALSE POSITIVE RATE: {fp_rate:.1f}%")
print(f"  (Evolution txs incorrectly flagged as attacks)")

# =============================================
# Create the plot
# =============================================
fig, ax = plt.subplots(figsize=(14, 7))

# Combine historical + new for full timeline
full_timeline = np.concatenate([historical_txs, new_amounts])
n_total = len(full_timeline)

# Plot historical (gray - baseline period)
ax.scatter(range(n_historical), historical_txs, 
           c='gray', alpha=0.5, s=40, label=f'Historical (n={n_historical})', zorder=2)

# Plot normal new (blue)
new_normal_idx = np.array(normal_indices) + n_historical
ax.scatter(new_normal_idx, normal_txs, 
           c='blue', alpha=0.7, s=50, label=f'Normal (n={n_normal})', zorder=3)

# Plot evolution (orange - legitimate but flagged!)
new_evolution_idx = np.array(evolution_indices) + n_historical
ax.scatter(new_evolution_idx, evolution_txs, 
           c='orange', alpha=0.8, s=60, label=f'Evolution (n={n_evolution}) - FALSE POSITIVES', zorder=4)

# Plot attacks (red)
new_attack_idx = np.array(attack_indices) + n_historical
ax.scatter(new_attack_idx, attack_txs, 
           c='red', alpha=0.7, s=50, label=f'Attack (n={n_attack})', zorder=3)

# Draw threshold lines
ax.axhline(y=baseline_mean, color='black', linestyle='-', linewidth=2, 
           label=f'Baseline Mean: ${baseline_mean:.0f}')
ax.axhline(y=upper_threshold, color='red', linestyle='--', linewidth=2,
           label=f'Upper (mean+2σ): ${upper_threshold:.0f}')
ax.axhline(y=lower_threshold, color='green', linestyle='--', linewidth=2,
           label=f'Lower (mean-2σ): ${lower_threshold:.0f}')

# Vertical line separating baseline period from new
ax.axvline(x=n_historical, color='purple', linestyle=':', linewidth=2, alpha=0.7)
ax.text(n_historical + 1, 50, 'Baseline\nperiod ends', fontsize=9, color='purple')

# Labels and title
ax.set_xlabel('Transaction Index', fontsize=12)
ax.set_ylabel('Amount ($)', fontsize=12)
ax.set_title(f'Phase 1: Static 2σ Baseline - The Rigidity Problem (FP Rate: {fp_rate:.1f}%)', 
             fontsize=14, fontweight='bold')

# Move legend outside plot
ax.legend(loc='upper left', fontsize=9, framealpha=0.9, bbox_to_anchor=(0, 1))
ax.grid(True, alpha=0.3)

# Set axis limits
ax.set_ylim(-50, 750)
ax.set_xlim(-5, n_total + 5)

# Add annotations
ax.annotate('Orange dots = FALSE POSITIVES\n(legitimate evolution flagged)', 
            xy=(new_evolution_idx[0], evolution_txs[0]), 
            xytext=(n_historical + 5, 280),
            fontsize=10, color='darkorange', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='darkorange', alpha=0.8))

plt.tight_layout()

# Save the figure
plt.savefig('tests/phase1_rigidity.png', dpi=150, bbox_inches='tight')
print(f"\nSaved: tests/phase1_rigidity.png")

plt.show()
