"""Main entry point for the MCP Payments Simulator.

This module sets up the FastMCP server and defines the tools available for
simulating payment workflows, fraud scoring, and consensus voting.
"""

import hashlib
import math
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from fastmcp import FastMCP

from consensus import ConsensusEngine, ConsensusResult
from database import DatabaseManager

# Initialize core components.
mcp = FastMCP("payments-simulator")
db = DatabaseManager()

# Test state for simulating tampering
_tampered_agents = set()


@mcp.tool()
def create_merchant_locked_card(merchant: str, amount: float) -> str:
    """Creates a merchant-locked virtual card with a spending limit.

    Args:
        merchant: The merchant name to lock the card to.
        amount: Spending limit for the card.

    Returns:
        A status message containing virtual card details or a detailed error message.
    """
    # Defensive input validation.
    if not merchant or not merchant.strip():
        return "Error: Merchant name required"
    if amount <= 0:
        return "Error: Amount must be positive"

    # Evaluate risk before proceeding.
    current_hour = datetime.now().hour
    risk = _calculate_fraud_score(amount, merchant.strip(), current_hour)

    if risk["score"] > 70:
        return (f"Card creation BLOCKED: Fraud score too high ({risk['score']}/100). "
                f"Reason: {risk['reason']}")

    if risk["score"] >= 30:
        return (f"Card requires MANUAL REVIEW: Fraud score {risk['score']}/100. "
                f"Reason: {risk['reason']}. Please contact support.")

    # Generate card attributes.
    card_suffix = f"{random.randint(0, 9999):04d}"
    card_number = f"4000-00{card_suffix}-0000-0000"
    expiry_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    mandate_id = f"mandate_{random.randint(100000, 999999)}"

    # Persist the mandate.
    db.create_mandate(mandate_id, card_number, amount, merchant)

    return (f"Card created successfully.\n"
            f"Number: {card_number}\n"
            f"Merchant: {merchant}\n"
            f"Limit: ${amount:.2f}\n"
            f"Expires: {expiry_date}\n"
            f"Risk Level: LOW ({risk['score']}/100)")


@mcp.tool()
async def get_receipts(customer_email: str, days: int = 7) -> str:
    """Retrieves simulated recent receipts for a customer.

    Args:
        customer_email: The customer's email address.
        days: Historical window in days (default 7).

    Returns:
        A formatted string listing the receipts.
    """
    # Simulate data fetching for demonstration.
    merchants = ["Amazon", "Netflix", "Stripe", "Uber", "GitHub"]
    receipts = []
    for _ in range(3):
        receipt_date = datetime.now() - timedelta(days=random.randint(0, days))
        receipts.append({
            "amount": round(random.uniform(5.00, 500.00), 2),
            "merchant": random.choice(merchants),
            "date": receipt_date.strftime("%Y-%m-%d")
        })

    lines = [f"Receipts for {customer_email}:"]
    for r in receipts:
        lines.append(f"- ${r['amount']:.2f} | {r['merchant']} | {r['date']}")

    return "\n".join(lines)


@mcp.tool()
async def execute_with_consensus(amount: float, merchant: str) -> str:
    """Executes a transaction via multi-agent consensus voting with integrity checks.

    This tool evaluates agent integrity before consensus. Agents failing integrity 
    checks are automatically revoked and excluded from the voting pool.

    Args:
        amount: The monetary amount of the transaction.
        merchant: The name of the merchant involved.

    Returns:
        A detailed report of the consensus voting process and final transaction status.
    """
    # Use the ConsensusEngine for evaluation.
    threshold = 0.67 if amount <= 1000 else 0.80
    engine = ConsensusEngine(threshold=threshold)
    
    # Auto-approval bypass for trivial amounts.
    if amount < 100:
        tx_id = f"tx_{hash(f'{amount}{merchant}{datetime.now()}') % 10**8:08d}"
        status = "approved"
        db.log_transaction(tx_id, amount, merchant, status)
        return (f"Transaction Record: {tx_id}\n"
                f"Amount: ${amount:.2f}\n"
                f"Merchant: {merchant}\n"
                f"Status: {status.upper()}\n"
                f"Consensus: Auto-approved (amount < $100)\n"
                f"Details: Threshold bypass")

    # Integrity Check & Revocation
    active_agents = []
    revocation_log = []
    
    for agent in engine.agents:
        agent_id = agent["id"]
        
        # Skip if already revoked
        if db.is_agent_revoked(agent_id):
            revocation_log.append(f"  - {agent_id}: EXCLUDED (Previously Revoked)")
            continue
            
        # Get last known hash (mocked - in production this comes from a secure store)
        last_known_hash = await _get_model_weight_hash(agent_id)
        
        # Evaluate integrity
        integrity = await _evaluate_agent_integrity(agent_id, amount, last_known_hash)
        
        if integrity["action"] == "REVOKE":
            db.revoke_agent(agent_id, "Compromised: Dual-signal detection triggered")
            revocation_log.append(f"  - {agent_id}: COMPROMISED (Revoking now)")
        else:
            active_agents.append(agent)
            if integrity["action"] == "HOLD_ALERT":
                revocation_log.append(f"  - {agent_id}: ALERT (Behavioral drift detected)")

    if not active_agents:
        return "Transaction BLOCKED: All consensus agents are currently revoked or compromised."

    # Perform consensus only with non-revoked agents
    # We temporarily override the engine's agents for this transaction
    original_agents = engine.agents
    engine.agents = active_agents
    
    result = engine.simulate_vote(amount, merchant)
    engine.agents = original_agents # Restore
    
    tx_id = result["transaction_id"]
    status = result["status"]
    
    # Log individual agent behaviors for auditing.
    for vote in result["votes"]:
        db.log_agent_vote(vote["agent_id"], tx_id, vote["vote"], amount)
    
    # Build detailed report
    agent_reports = []
    for v in result["votes"]:
        agent_reports.append(f"  - {v['agent_id']}: {v['vote'].upper()} ({v['reason']})")
    
    if revocation_log:
        agent_reports.insert(0, "Security Events:")
        agent_reports.extend(["", "Active Votes:"])

    # Persist the final transaction state.
    db.log_transaction(tx_id, amount, merchant, status)

    return (f"Transaction Record: {tx_id}\n"
            f"Amount: ${amount:.2f}\n"
            f"Merchant: {merchant}\n"
            f"Status: {status.upper()}\n"
            f"Consensus: {result['approval_rate']*100:.0f}% approval (Threshold: {result['required_threshold']*100:.0f}%)\n"
            f"Details:\n{chr(10).join(revocation_log + agent_reports)}")


def _calculate_fraud_score(amount: float, merchant: str, hour: int) -> Dict[str, Any]:
    """Internal logic for calculating multi-dimensional fraud scores.

    Args:
        amount: The transaction amount to evaluate.
        merchant: The merchant name involved in the transaction.
        hour: The UTC hour of the transaction (expected range: 0-23).

    Returns:
        A dictionary containing the calculated fraud 'score' (0-100), 'level'
        (low/medium/high), and qualitative 'reason' justifying the score.
    """
    known_merchants = {"amazon", "netflix", "stripe", "uber", "github", "apple", "google"}
    typical_spend = {"netflix": 15, "spotify": 10, "amazon": 50, "uber": 25}

    # 1. Volume-based scoring (max 40 pts).
    amount_score = min(amount / 125, 40)

    # 2. Time-of-day scoring (max 30 pts). Late night increases risk.
    time_score = 30 if 0 <= hour <= 5 else 0

    # 3. Reputation scoring (max 30 pts). Unrecognized merchants increase risk.
    merchant_score = 30 if merchant.lower() not in known_merchants else 0

    # 4. Anomaly detection (max 25 pts). Checks for deviations from typical spend.
    typical = typical_spend.get(merchant.lower(), 50)
    anomaly_score = 25 if amount > (typical * 20) else 0

    total_score = round(min(amount_score + time_score + merchant_score + anomaly_score, 100), 1)

    if total_score < 30:
        level = "low"
    elif total_score <= 60:
        level = "medium"
    else:
        level = "high"

    # Compile qualitative reasons.
    reasons = []
    if amount_score >= 10: reasons.append("Significant amount")
    if time_score > 0: reasons.append("Suspicious hour detected")
    if merchant_score > 0: reasons.append("Unverified merchant")
    if anomaly_score > 0: reasons.append(f"Spend Anomaly for {merchant}")
    
    reason_str = " + ".join(reasons) if reasons else "Consistent with typical patterns"

    return {
        "score": total_score,
        "level": level,
        "reason": reason_str
    }


@mcp.tool()
async def get_fraud_score(amount: float, merchant: str, hour: int) -> str:
    """Provides a concise fraud risk score for a transaction.

    Args:
        amount: The transaction amount.
        merchant: The merchant name.
        hour: The UTC hour of the transaction (0-23).

    Returns:
        A formatted string with the risk assessment.
    """
    result = _calculate_fraud_score(amount, merchant, hour)
    
    return (f"Risk Assessment:\n"
            f"Score: {result['score']}/100\n"
            f"Level: {result['level'].upper()}\n"
            f"Reason: {result['reason']}")


@mcp.tool()
async def score_payment_risk(amount: float, merchant: str, hour: int) -> str:
    """Scores a payment for fraud risk and provides a recommendation.

    Args:
        amount: The transaction amount.
        merchant: The merchant name.
        hour: The UTC hour of the transaction (0-23).

    Returns:
        A formatted risk assessment report.
    """
    if not merchant or not merchant.strip():
        return "Error: Merchant name required"
    if amount <= 0:
        return "Error: Amount must be positive"
    if not (0 <= hour <= 23):
        return "Error: Hour must be UTC (0-23)"

    result = _calculate_fraud_score(amount, merchant.strip(), hour)
    
    recommendation = "Auto-approve"
    if result["score"] > 60:
        recommendation = "Block"
    elif result["score"] >= 30:
        recommendation = "Review"

    return (f"Risk Assessment Report\n"
            f"----------------------\n"
            f"Score: {result['score']}/100\n"
            f"Risk Level: {result['level'].upper()}\n"
            f"Reasons: {result['reason']}\n"
            f"Recommendation: {recommendation}")


@mcp.tool()
async def get_agent_status() -> str:
    """Checks and reports the operational health of all consensus agents.

    Returns:
        A formatted status report detailing the health and trust score of the agent fleet.
    """
    engine = ConsensusEngine()
    lines = ["System Agent Status Report", "=" * 30]

    for agent in engine.agents:
        is_healthy = random.random() < 0.95
        status_text = "OPERATIONAL" if is_healthy else "DEGRADED"
        health_label = "HEALTHY" if is_healthy else "ALERT"
        
        lines.append(f"ID: {agent['id']} | [{health_label}]")
        lines.append(f"  Name: {agent['name']}")
        lines.append(f"  Status: {status_text}")
        lines.append(f"  Trust Score: {agent['trust_score']}")
        lines.append("")


    return "\n".join(lines)


@mcp.tool()
async def get_exponential_baseline(agent_id: str, decay: float = 0.9) -> Dict[str, Any]:
    """Calculates an adaptive baseline using Exponentially Weighted Moving Average.

    This baseline prioritizes recent transaction behavior, allowing detection
    thresholds to adapt to legitimate shifting patterns while maintaining sensitivity.

    Args:
        agent_id: Unique identifier for the agent being evaluated.
        decay: Decay factor between 0.0 and 1.0. Higher values weight recent data more.

    Returns:
        A dictionary containing the calculated 'ewma' and the total 'sample_count'.
    """
    amounts = db.get_recent_approved_amounts(agent_id, limit=100)
    
    if not amounts:
        return {"ewma": 0.0, "sample_count": 0}
    
    weighted_sum = 0.0
    weight_total = 0.0
    
    for i, amount in enumerate(amounts):
        weight = decay ** i
        weighted_sum += amount * weight
        weight_total += weight
    
    ewma = weighted_sum / weight_total if weight_total > 0 else 0.0
    
    return {"ewma": round(ewma, 2), "sample_count": len(amounts)}


async def _get_model_weight_hash(agent_id: str) -> str:
    """Internal implementation for getting model weight hash."""
    return hashlib.sha256(f"{agent_id}-model-v1.3".encode()).hexdigest()

@mcp.tool()
async def get_model_weight_hash(agent_id: str) -> str:
    """Returns a cryptographic hash representing the agent's model weights.

    This mocks a model registry verify service. The hash can be used to detect 
    unauthorized modifications to the agent's underlying model weights.

    Args:
        agent_id: Unique identifier for the agent being checked.

    Returns:
        A SHA-256 hash string of the agent's model version.
    """
    return await _get_model_weight_hash(agent_id)


async def _has_weights_tampered(agent_id: str, last_known_hash: str) -> bool:
    """Internal implementation for checking weight tampering."""
    if agent_id in _tampered_agents:
        return True
    current_hash = await _get_model_weight_hash(agent_id)
    return current_hash != last_known_hash

@mcp.tool()
async def has_weights_tampered(agent_id: str, last_known_hash: str) -> bool:
    """Checks if an agent's model weights have been tampered with.

    Compares the current live model hash against a previously recorded value.
    A mismatch indicates potential compromise vs. legitimate behavioral drift.

    Args:
        agent_id: Unique identifier for the agent.
        last_known_hash: The cryptographic hash recorded before the current transaction.

    Returns:
        True if the current hash differs from the recorded hash, False otherwise.
    """
    return await _has_weights_tampered(agent_id, last_known_hash)


@mcp.tool()
async def simulate_tampering(agent_id: str) -> str:
    """Directly simulates model tampering for an agent (TEST TOOL).

    Args:
        agent_id: Unique identifier for the agent to tamper.

    Returns:
        A status message.
    """
    _tampered_agents.add(agent_id)
    return f"Tampering simulated for agent {agent_id}."


async def _evaluate_agent_integrity(
    agent_id: str, current_vote_amount: float, last_known_hash: str
) -> Dict[str, str]:
    """Internal implementation for evaluating agent integrity."""
    # 1. Behavioral Check (Exponentially Weighted)
    # Get recent behavior for adaptive baseline
    historical_amounts = db.get_recent_approved_amounts(agent_id, limit=50)
    
    # Calculate adaptive baseline (EWMA)
    decay = 0.9
    if not historical_amounts:
        ewma = current_vote_amount
    else:
        weighted_sum = 0.0
        weight_total = 0.0
        for i, amount in enumerate(historical_amounts):
            weight = decay ** i
            weighted_sum += amount * weight
            weight_total += weight
        ewma = weighted_sum / weight_total
    
    drift = abs(current_vote_amount - ewma)
    behavioral_anomaly = drift > (0.5 * ewma) if ewma > 0 else False
    
    # 2. Cryptographic Check
    hash_tampered = await _has_weights_tampered(agent_id, last_known_hash)
    
    # Dual-Signal Logic Matrix
    if behavioral_anomaly and hash_tampered:
        return {"action": "REVOKE", "confidence": "HIGH"}
    elif behavioral_anomaly:
        # Behavioral drift without tampering -> Legitimate evolution or subtle attack
        return {"action": "HOLD_ALERT", "confidence": "MEDIUM"}
    elif hash_tampered:
        # Weight change without behavioral drift -> Model update or dormant compromise
        return {"action": "IGNORE", "confidence": "LOW"}
    else:
        return {"action": "APPROVE", "confidence": "HIGH"}

@mcp.tool()
async def evaluate_agent_integrity(
    agent_id: str, current_vote_amount: float, last_known_hash: str
) -> Dict[str, str]:
    """Evaluates agent integrity using behavioral and cryptographic signals.

    This dual-signal approach distinguishes between legitimate behavioral evolution
    and malicious compromise by correlating behavioral drift with weight tampering.

    Args:
        agent_id: Unique identifier for the agent.
        current_vote_amount: Amount of the current transaction being voted on.
        last_known_hash: The model hash from the last known good state.

    Returns:
        A dictionary with 'action' (REVOKE, HOLD_ALERT, IGNORE, or APPROVE) 
        and the associated 'confidence' level (HIGH, MEDIUM, or LOW).
    """
    return await _evaluate_agent_integrity(agent_id, current_vote_amount, last_known_hash)


# --- REDACTED: Static baseline inflated by attack data -> 25% FP on evolution
# Methodology flaw: calculated threshold using all data (including attacks)
# Result: mean=$198, 2σ=$601, artificially low FP of 0%
# Realistic test: clean baseline mean=$97, 2σ=$124 -> 25% FP on legitimate evolution
# See phase1_rigidity.png for visual proof of rigidity
# ---

# def _calculate_sigma_baseline(agent_id: str) -> Dict[str, float]:
#     """Helper for calculating behavioral baseline using standard deviation.
#
#     Args:
#         agent_id: The identifier for the agent.
#
#     Returns:
#         A dictionary containing the mean and sigma (standard deviation).
#     """
#     amounts = db.get_agent_approved_amounts(agent_id)
#     n = len(amounts)
#     
#     if n == 0:
#         return {"mean": 0.0, "sigma": 0.0}
#     
#     mean = sum(amounts) / n
#     if n < 2:
#         return {"mean": mean, "sigma": 0.0}
#     
#     variance = sum((x - mean) ** 2 for x in amounts) / (n - 1)
#     sigma = math.sqrt(variance)
#     
#     return {"mean": mean, "sigma": sigma}
#
#
# @mcp.tool()
# async def get_behavioral_baseline(agent_id: str) -> Dict[str, float]:
#     """Calculates the behavioral baseline for an agent based on approval history.
#
#     Args:
#         agent_id: The agent's identifier.
#
#     Returns:
#         A dict with 'mean' and 'sigma' (standard deviation).
#     """
#     return _calculate_sigma_baseline(agent_id)
#
#
# @mcp.tool()
# async def should_revoke_agent(agent_id: str, current_vote_amount: float) -> str:
#     """Evaluates behavioral drift to decide if an agent's access should be revoked.
#
#     Calculates the deviation of the current vote from the agent's historical
#     mean. Drifts exceeding 2*sigma results in revocation.
#
#     Args:
#         agent_id: The agent's identifier.
#         current_vote_amount: Amount of the current transaction.
#
#     Returns:
#         Status indicator: 'REVOKE', 'HOLD' (if insufficient data), or 'APPROVE'.
#     """
#     baseline = _calculate_sigma_baseline(agent_id)
#     mean = baseline["mean"]
#     sigma = baseline["sigma"]
#     
#     # Insufficient historical data to establish a reliable baseline.
#     if sigma == 0:
#         return "HOLD"
#     
#     drift = abs(current_vote_amount - mean)
#     
#     # 2-sigma threshold for anomaly detection.
#     if drift > 2.0 * sigma:
#         return "REVOKE"
#     
#     return "APPROVE"


@mcp.tool()
async def get_compromised_agents() -> str:
    """Lists all agents that have been automatically or manually revoked.

    Returns:
        A list of revoked agents and the reasons for their revocation.
    """
    revoked = db.get_revoked_agents()
    if not revoked:
        return "No agents are currently revoked."
    
    lines = ["Revoked Agents Report", "=" * 30]
    for r in revoked:
        lines.append(f"ID: {r['agent_id']}")
        lines.append(f"  Reason: {r['reason']}")
        lines.append(f"  Revoked At: {r['revoked_at']}")
        lines.append("")
        
    return "\n".join(lines)


@mcp.tool()
async def reinstate_agent(agent_id: str) -> str:
    """Restores a revoked agent to operational status.

    Args:
        agent_id: The unique identifier for the agent to reinstate.

    Returns:
        A status message confirming the restoration.
    """
    if not db.is_agent_revoked(agent_id):
        return f"Agent {agent_id} is not currently revoked."
    
    db.reinstate_agent(agent_id)
    return f"Agent {agent_id} has been successfully reinstated."


if __name__ == "__main__":
    # Start the MCP server.
    mcp.run(transport='sse', host='0.0.0.0', port=8765)
