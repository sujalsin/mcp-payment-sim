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


@mcp.tool()
def create_merchant_locked_card(merchant: str, amount: float) -> str:
    """Creates a merchant-locked virtual card with a spending limit.

    Args:
        merchant: The merchant name to lock the card to.
        amount: Spending limit for the card.

    Returns:
        A status message with card details or an error message.
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
    """Executes a transaction via multi-agent consensus voting.

    Args:
        amount: The transaction amount.
        merchant: The merchant name.

    Returns:
        A detailed summary of the consensus process and final status.
    """
    # Use the ConsensusEngine for evaluation.
    # Higher amounts require higher confirmation thresholds.
    threshold = 0.67 if amount <= 1000 else 0.80
    engine = ConsensusEngine(threshold=threshold)
    
    # Auto-approval bypass for trivial amounts.
    if amount < 100:
        tx_id = f"tx_{hash(f'{amount}{merchant}{datetime.now()}') % 10**8:08d}"
        status = "approved"
        approval_info = "Auto-approved (amount < $100)"
        agent_details = "Agents: N/A (Threshold bypass)"
    else:
        result = engine.simulate_vote(amount, merchant)
        tx_id = result["transaction_id"]
        status = result["status"]
        
        # Log individual agent behaviors for auditing and fingerprinting.
        for vote in result["votes"]:
            db.log_agent_vote(vote["agent_id"], tx_id, vote["vote"], amount)
        
        # Build detailed agent voting report
        agent_details_list = []
        for v in result["votes"]:
            agent_details_list.append(f"  - {v['agent_id']}: {v['vote'].upper()} ({v['reason']})")
        
        votes_report = "\n".join(agent_details_list)

        approve_count = sum(1 for v in result["votes"] if v["vote"] == "approve")
        total_votes = len(result["votes"])

        # Persist the final transaction state.
        db.log_transaction(tx_id, amount, merchant, status)

        return (f"Transaction Record: {tx_id}\n"
                f"Amount: ${amount:.2f}\n"
                f"Merchant: {merchant}\n"
                f"Status: {result['status'].upper()}\n"
                f"Consensus: {approve_count}/{total_votes} approvals\n"
                f"Agents:\n{votes_report}")

    # Persist the final transaction state for auto-approved transactions.
    db.log_transaction(tx_id, amount, merchant, status)

    return (f"Transaction Record: {tx_id}\n"
            f"Amount: ${amount:.2f}\n"
            f"Merchant: {merchant}\n"
            f"Status: {status.upper()}\n"
            f"Consensus: {approval_info}\n"
            f"Details: {agent_details}")


def _calculate_fraud_score(amount: float, merchant: str, hour: int) -> Dict[str, Any]:
    """Internal logic for calculating multi-dimensional fraud scores.

    Args:
        amount: The transaction amount.
        merchant: The merchant name.
        hour: The UTC hour of the transaction (0-23).

    Returns:
        A result dictionary with the score, risk level, and reasons.
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
    """Checks and reports the operational status of all consensus agents.

    Returns:
        A formatted status report for the agent fleet.
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
    """Calculates an exponentially weighted moving average baseline for an agent.

    This adaptive baseline gives more weight to recent transactions, allowing
    it to drift with legitimate behavioral evolution and reducing false positives.

    Args:
        agent_id: The agent's identifier.
        decay: The decay factor (0-1). Higher values weight recent data more.

    Returns:
        A dictionary with 'ewma' (the weighted average) and 'sample_count'.
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


@mcp.tool()
async def get_model_weight_hash(agent_id: str) -> str:
    """Returns a cryptographic hash representing the agent's model weights.

    This mocks a real model registry that tracks agent versions. The hash
    can be used to detect if an agent's underlying model has been tampered with.

    Args:
        agent_id: The agent's identifier.

    Returns:
        A SHA-256 hash string of the agent's model version.
    """
    return hashlib.sha256(f"{agent_id}-model-v1.3".encode()).hexdigest()


@mcp.tool()
async def has_weights_tampered(agent_id: str, last_known_hash: str) -> bool:
    """Checks if an agent's model weights have been tampered with.

    Compares the current model hash against a previously recorded hash.
    A mismatch indicates potential compromise (vs. legitimate behavioral drift).

    Args:
        agent_id: The agent's identifier.
        last_known_hash: The previously recorded hash to compare against.

    Returns:
        True if the hashes don't match (tampered), False otherwise.
    """
    current_hash = hashlib.sha256(f"{agent_id}-model-v1.3".encode()).hexdigest()
    return current_hash != last_known_hash


@mcp.tool()
async def evaluate_agent_integrity(
    agent_id: str, current_vote_amount: float, last_known_hash: str
) -> Dict[str, str]:
    """Evaluates an agent's integrity using behavioral and cryptographic signals.

    Combines exponential baseline drift detection with model hash verification
    to make high-confidence revocation decisions, reducing false positives.

    Args:
        agent_id: The agent's identifier.
        current_vote_amount: Amount of the current transaction being evaluated.
        last_known_hash: Previously recorded model hash for comparison.

    Returns:
        A dict with 'action' (REVOKE/HOLD_ALERT/IGNORE/APPROVE) and 'confidence'.
    """
    # Get adaptive baseline
    baseline_result = await get_exponential_baseline(agent_id, 0.9)
    baseline = baseline_result["ewma"]
    
    # Calculate behavioral drift
    drift = abs(current_vote_amount - baseline)
    behavioral_anomaly = drift > (0.5 * baseline) if baseline > 0 else False
    
    # Check cryptographic integrity
    hash_tampered = await has_weights_tampered(agent_id, last_known_hash)
    
    # Decision matrix: only auto-revoke when BOTH signals confirm compromise
    if behavioral_anomaly and hash_tampered:
        return {"action": "REVOKE", "confidence": "HIGH"}
    elif behavioral_anomaly and not hash_tampered:
        return {"action": "HOLD_ALERT", "confidence": "MEDIUM"}
    elif not behavioral_anomaly and hash_tampered:
        return {"action": "IGNORE", "confidence": "LOW"}
    else:
        return {"action": "APPROVE", "confidence": "HIGH"}


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


if __name__ == "__main__":
    # Start the MCP server.
    mcp.run(transport='sse', host='0.0.0.0', port=8765)
