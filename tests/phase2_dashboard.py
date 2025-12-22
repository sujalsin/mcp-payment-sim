"""Dashboard visualization for Phase 2 improvement metrics.

This script generates a comprehensive 2x2 dashboard showing the improvement
from Phase 1 (static 2-sigma) to Phase 2 (dual-signal) detection.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


def simulate_ewma_baseline(amounts: list, decay: float = 0.9) -> float:
    """Calculates exponentially weighted moving average."""
    if not amounts:
        return 0.0
    weighted_sum = sum(amt * (decay ** i) for i, amt in enumerate(amounts))
    weight_total = sum(decay ** i for i in range(len(amounts)))
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


def plot_improvement_metrics():
    """Generates a 2x2 dashboard showing Phase 1 vs Phase 2 improvements."""
    
    np.random.seed(42)
    
    # Generate production-scale dataset
    n_historical = 100
    historical_txs = np.random.normal(100, 15, n_historical)
    ewma_baseline = simulate_ewma_baseline(list(reversed(historical_txs)))
    static_threshold = np.mean(historical_txs) + 2 * np.std(historical_txs)
    
    n_normal = 8000
    n_evolution = 1500
    n_attack = 500
    
    normal_txs = np.random.normal(100, 15, n_normal)
    evolution_txs = np.random.normal(150, 25, n_evolution)
    attack_txs = np.random.normal(600, 50, n_attack)
    
    # Create labeled dataset
    all_txs = []
    for i, tx in enumerate(normal_txs):
        all_txs.append({'amount': tx, 'is_attack': False, 'is_evolution': False})
    for i, tx in enumerate(evolution_txs):
        all_txs.append({'amount': tx, 'is_attack': False, 'is_evolution': True})
    for i, tx in enumerate(attack_txs):
        all_txs.append({'amount': tx, 'is_attack': True, 'is_evolution': False})
    
    np.random.shuffle(all_txs)
    
    # Calculate metrics for both phases
    phase1_tp, phase1_fp, phase1_tn, phase1_fn = 0, 0, 0, 0
    phase2_tp, phase2_fp, phase2_tn, phase2_fn = 0, 0, 0, 0
    
    phase1_decisions = {'REVOKE': 0, 'APPROVE': 0}
    phase2_decisions = {'REVOKE': 0, 'HOLD_ALERT': 0, 'IGNORE': 0, 'APPROVE': 0}
    
    # Track cumulative FP rates
    phase1_cumulative_fp = []
    phase2_cumulative_fp = []
    phase1_running_fp = 0
    phase2_running_fp = 0
    phase1_running_legitimate = 0
    phase2_running_legitimate = 0
    
    for i, tx in enumerate(all_txs):
        # Phase 1: Static threshold
        phase1_revoked = tx['amount'] > static_threshold
        
        if tx['is_attack']:
            if phase1_revoked:
                phase1_tp += 1
            else:
                phase1_fn += 1
        else:
            phase1_running_legitimate += 1
            if phase1_revoked:
                phase1_fp += 1
                phase1_running_fp += 1
                phase1_decisions['REVOKE'] += 1
            else:
                phase1_tn += 1
                phase1_decisions['APPROVE'] += 1
        
        # Phase 2: Dual-signal
        hash_tampered = tx['is_attack']
        result = evaluate_phase2_integrity(ewma_baseline, tx['amount'], hash_tampered)
        phase2_revoked = (result['action'] == 'REVOKE')
        phase2_decisions[result['action']] += 1
        
        if tx['is_attack']:
            if phase2_revoked:
                phase2_tp += 1
            else:
                phase2_fn += 1
        else:
            phase2_running_legitimate += 1
            if phase2_revoked:
                phase2_fp += 1
                phase2_running_fp += 1
            else:
                phase2_tn += 1
        
        # Track cumulative FP rates
        if phase1_running_legitimate > 0:
            phase1_cumulative_fp.append(phase1_running_fp / phase1_running_legitimate * 100)
        else:
            phase1_cumulative_fp.append(0)
        
        if phase2_running_legitimate > 0:
            phase2_cumulative_fp.append(phase2_running_fp / phase2_running_legitimate * 100)
        else:
            phase2_cumulative_fp.append(0)
    
    # Calculate final metrics
    phase1_precision = phase1_tp / (phase1_tp + phase1_fp) if (phase1_tp + phase1_fp) > 0 else 0
    phase1_recall = phase1_tp / (phase1_tp + phase1_fn) if (phase1_tp + phase1_fn) > 0 else 0
    phase2_precision = phase2_tp / (phase2_tp + phase2_fp) if (phase2_tp + phase2_fp) > 0 else 0
    phase2_recall = phase2_tp / (phase2_tp + phase2_fn) if (phase2_tp + phase2_fn) > 0 else 0
    
    # Create figure
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle('Phase 2 Improvement Dashboard: Dual-Signal Detection', fontsize=16, fontweight='bold')
    
    # ===== TOP-LEFT: Precision/Recall Bar Chart =====
    ax1 = axes[0, 0]
    x = np.arange(2)
    width = 0.35
    
    phase1_metrics = [phase1_precision * 100, phase1_recall * 100]
    phase2_metrics = [phase2_precision * 100, phase2_recall * 100]
    
    bars1 = ax1.bar(x - width/2, phase1_metrics, width, label='Phase 1 (Static)', color='#e74c3c', alpha=0.8)
    bars2 = ax1.bar(x + width/2, phase2_metrics, width, label='Phase 2 (Adaptive)', color='#27ae60', alpha=0.8)
    
    ax1.set_ylabel('Percentage (%)')
    ax1.set_title('Detection Quality: Phase 1 vs Phase 2', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(['Precision', 'Recall'])
    ax1.set_ylim(0, 110)
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # Add value labels
    for bar, val in zip(bars1, phase1_metrics):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, f'{val:.0f}%', 
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    for bar, val in zip(bars2, phase2_metrics):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, f'{val:.0f}%', 
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # ===== TOP-RIGHT: Confusion Matrix Comparison =====
    ax2 = axes[0, 1]
    
    # Create side-by-side confusion matrices
    phase1_matrix = np.array([[phase1_tp, phase1_fp], [phase1_fn, phase1_tn]])
    phase2_matrix = np.array([[phase2_tp, phase2_fp], [phase2_fn, phase2_tn]])
    
    # Plot Phase 1
    ax2_left = ax2.inset_axes([0.05, 0.1, 0.4, 0.8])
    im1 = ax2_left.imshow(phase1_matrix, cmap='Reds', aspect='auto')
    ax2_left.set_xticks([0, 1])
    ax2_left.set_yticks([0, 1])
    ax2_left.set_xticklabels(['Revoked', 'Not Rev.'], fontsize=8)
    ax2_left.set_yticklabels(['Attack', 'Legit.'], fontsize=8)
    ax2_left.set_title('Phase 1', fontsize=10, fontweight='bold')
    for i in range(2):
        for j in range(2):
            ax2_left.text(j, i, f'{phase1_matrix[i, j]:,}', ha='center', va='center', 
                         color='white' if phase1_matrix[i, j] > 500 else 'black', fontweight='bold')
    
    # Plot Phase 2
    ax2_right = ax2.inset_axes([0.55, 0.1, 0.4, 0.8])
    im2 = ax2_right.imshow(phase2_matrix, cmap='Greens', aspect='auto')
    ax2_right.set_xticks([0, 1])
    ax2_right.set_yticks([0, 1])
    ax2_right.set_xticklabels(['Revoked', 'Not Rev.'], fontsize=8)
    ax2_right.set_yticklabels(['Attack', 'Legit.'], fontsize=8)
    ax2_right.set_title('Phase 2', fontsize=10, fontweight='bold')
    for i in range(2):
        for j in range(2):
            ax2_right.text(j, i, f'{phase2_matrix[i, j]:,}', ha='center', va='center', 
                          color='white' if phase2_matrix[i, j] > 500 else 'black', fontweight='bold')
    
    ax2.set_title('False Positive Reduction', fontweight='bold')
    ax2.axis('off')
    
    # Add annotation
    fp_reduction = phase1_fp - phase2_fp
    ax2.text(0.5, 0.02, f'FP Reduction: {phase1_fp:,} -> {phase2_fp:,} ({fp_reduction:,} eliminated)', 
            ha='center', fontsize=11, fontweight='bold', color='#27ae60', transform=ax2.transAxes)
    
    # ===== BOTTOM-LEFT: Cumulative FP Rate Over Time =====
    ax3 = axes[1, 0]
    
    # Sample every 100 for visualization
    sample_indices = list(range(0, len(all_txs), 100))
    phase1_sampled = [phase1_cumulative_fp[i] for i in sample_indices]
    phase2_sampled = [phase2_cumulative_fp[i] for i in sample_indices]
    
    ax3.plot(sample_indices, phase1_sampled, color='#e74c3c', linewidth=2, label='Phase 1 (Static)')
    ax3.plot(sample_indices, phase2_sampled, color='#27ae60', linewidth=2, label='Phase 2 (Adaptive)')
    ax3.fill_between(sample_indices, phase1_sampled, phase2_sampled, alpha=0.2, color='#27ae60')
    
    ax3.set_xlabel('Transaction Index')
    ax3.set_ylabel('Cumulative FP Rate (%)')
    ax3.set_title('Cumulative FP Rate: Phase 2 Eliminates False Auto-Revokes', fontweight='bold')
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(0, max(phase1_sampled) * 1.1)
    
    # ===== BOTTOM-RIGHT: Decision Distribution Pie Charts =====
    ax4 = axes[1, 1]
    
    # Phase 1 pie
    ax4_left = ax4.inset_axes([0.0, 0.1, 0.45, 0.8])
    phase1_sizes = [phase1_decisions['REVOKE'], phase1_decisions['APPROVE']]
    phase1_labels = ['Auto-Revoke', 'Approve']
    phase1_colors = ['#e74c3c', '#3498db']
    wedges1, texts1, autotexts1 = ax4_left.pie(phase1_sizes, labels=phase1_labels, colors=phase1_colors, 
                                               autopct='%1.1f%%', startangle=90, explode=(0.05, 0))
    ax4_left.set_title('Phase 1', fontsize=10, fontweight='bold')
    
    # Phase 2 pie
    ax4_right = ax4.inset_axes([0.55, 0.1, 0.45, 0.8])
    phase2_sizes = [phase2_decisions['REVOKE'], phase2_decisions['HOLD_ALERT'], 
                    phase2_decisions['IGNORE'], phase2_decisions['APPROVE']]
    phase2_labels = ['Revoke', 'Hold/Alert', 'Ignore', 'Approve']
    phase2_colors = ['#e74c3c', '#f39c12', '#95a5a6', '#3498db']
    # Filter out zero values
    phase2_sizes_filtered = []
    phase2_labels_filtered = []
    phase2_colors_filtered = []
    for s, l, c in zip(phase2_sizes, phase2_labels, phase2_colors):
        if s > 0:
            phase2_sizes_filtered.append(s)
            phase2_labels_filtered.append(l)
            phase2_colors_filtered.append(c)
    
    wedges2, texts2, autotexts2 = ax4_right.pie(phase2_sizes_filtered, labels=phase2_labels_filtered, 
                                                 colors=phase2_colors_filtered, autopct='%1.1f%%', 
                                                 startangle=90, explode=[0.05]*len(phase2_sizes_filtered))
    ax4_right.set_title('Phase 2', fontsize=10, fontweight='bold')
    
    ax4.set_title('From Auto-Revoke to Human Review', fontweight='bold')
    ax4.axis('off')
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    output_path = 'tests/phase2_metrics_dashboard.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"Dashboard saved to {output_path}")
    
    return output_path


if __name__ == "__main__":
    plot_improvement_metrics()
