from fastmcp import FastMCP
import sqlite3
import json
import random
import hashlib
from datetime import datetime, timedelta
from consensus import ConsensusEngine

# Initialize FastMCP server
mcp = FastMCP("payments-simulator")

# Database setup
def init_db():
    """Initialize SQLite database with required tables."""
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    
    # Create mandates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mandates (
            id TEXT PRIMARY KEY,
            agent_id TEXT,
            amount REAL,
            merchant TEXT,
            created_at TIMESTAMP
        )
    """)
    
    # Create transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            amount REAL,
            merchant TEXT,
            status TEXT,
            created_at TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()


@mcp.tool()
def create_merchant_locked_card(merchant: str, amount: float) -> str:
    """
    Create a merchant-locked virtual card for a specific merchant and spending limit.
    
    Args:
        merchant: The merchant name that the card is locked to.
        amount: The maximum spending limit for this card.
    
    Returns:
        A string containing the card details.
    """
    # Input validation
    if not merchant or not merchant.strip():
        return "Error: Merchant name required"
    if amount <= 0:
        return "Error: Amount must be positive"
    
    # Check fraud score first using current hour
    current_hour = datetime.now().hour
    risk = score_transaction(amount, merchant.strip(), current_hour)
    
    if risk['score'] > 70:
        return f"Card creation BLOCKED: fraud score too high ({risk['score']}/100)\nReason: {risk['reason']}"
    
    if risk['score'] >= 30:
        return f"Card requires MANUAL REVIEW: fraud score {risk['score']}/100\nReason: {risk['reason']}\nPlease contact support for approval."
    
    # Proceed with card creation for low-risk transactions
    random_digits = f"{random.randint(0, 9999):04d}"
    card_number = f"4000-00{random_digits}-0000-0000"
    
    expires = datetime.now() + timedelta(days=30)
    expires_str = expires.strftime("%Y-%m-%d")
    
    mandate_id = f"mandate_{random.randint(100000, 999999)}"
    
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO mandates (id, agent_id, amount, merchant, created_at) VALUES (?, ?, ?, ?, ?)",
        (mandate_id, card_number, amount, merchant, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    return f"Card created: {card_number}, Merchant: {merchant}, Limit: ${amount}, Expires: {expires_str}\nRisk Score: {risk['score']}/100 (LOW)"


def generate_fake_receipt(customer_email: str) -> dict:
    """Generate a fake receipt with random data."""
    merchants = ["Amazon", "Netflix", "Stripe", "Uber", "GitHub"]
    
    # Random date from last 30 days
    days_ago = random.randint(0, 30)
    receipt_date = datetime.now() - timedelta(days=days_ago)
    
    return {
        "id": f"receipt_{random.randint(10000, 99999)}",
        "amount": round(random.uniform(5.00, 500.00), 2),
        "merchant": random.choice(merchants),
        "date": receipt_date.strftime("%Y-%m-%d"),
        "email": customer_email
    }


@mcp.tool()
async def get_receipts(customer_email: str, days: int = 7) -> str:
    """
    Get recent receipts for a customer email.
    
    Args:
        customer_email: The customer's email address.
        days: Number of days to look back (default 7, not currently used for filtering).
    
    Returns:
        A formatted string with receipt details.
    """
    receipts = [generate_fake_receipt(customer_email) for _ in range(3)]
    
    lines = [f"Receipts for {customer_email}:"]
    for r in receipts:
        lines.append(f"- ${r['amount']:.2f} - {r['merchant']} - {r['date']}")
    
    return "\n".join(lines)


@mcp.tool()
async def execute_with_consensus(amount: float, merchant: str) -> str:
    """
    Execute a transaction with multi-agent consensus voting.
    
    Args:
        amount: The transaction amount.
        merchant: The merchant name.
    
    Returns:
        A formatted string with transaction details and approval status.
    """
    # Generate transaction ID from hash of amount + merchant
    tx_hash = hashlib.md5(f"{amount}{merchant}{datetime.now().isoformat()}".encode()).hexdigest()[:10]
    tx_id = f"tx_{tx_hash}"
    
    # Auto-approve small transactions
    if amount < 100:
        status = "approved"
        approval_info = "Auto-approved (amount < $100)"
        agent_details = "All agents: Auto-approved"
    else:
        # Use consensus engine for larger amounts
        engine = ConsensusEngine(threshold=0.67 if amount <= 1000 else 0.80)
        result = engine.simulate_vote(amount, merchant)
        
        approve_count = sum(1 for v in result["votes"] if v["vote"] == "approve")
        total_agents = len(result["votes"])
        
        # Map pending to rejected for final status
        status = result["status"] if result["status"] == "approved" else "rejected"
        approval_info = f"{approve_count} of {total_agents} agents approved ({int(result['approval_rate'] * 100)}%)"
        
        # Build agent voting details
        approved_agents = [v["agent_id"] for v in result["votes"] if v["vote"] == "approve"]
        rejected_agents = [v["agent_id"] for v in result["votes"] if v["vote"] == "reject"]
        review_agents = [v["agent_id"] for v in result["votes"] if v["vote"] == "review"]
        
        details = []
        if approved_agents:
            details.append(f"Approved: {', '.join(approved_agents)}")
        if rejected_agents:
            details.append(f"Rejected: {', '.join(rejected_agents)}")
        if review_agents:
            details.append(f"Review: {', '.join(review_agents)}")
        agent_details = " | ".join(details)
    
    # Save to database if approved
    if status == "approved":
        conn = sqlite3.connect("payments.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO transactions (id, amount, merchant, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (tx_id, amount, merchant, status, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    
    return f"""Transaction: {tx_id}
Amount: ${amount:.2f}
Merchant: {merchant}
Status: {status.upper()}
Approval: {approval_info}
Agents: {agent_details}"""


def score_transaction(amount: float, merchant: str, hour: int) -> dict:
    """
    Calculate a risk score for a transaction.
    
    Args:
        amount: The transaction amount.
        merchant: The merchant name.
        hour: The hour of the day (0-23) when the transaction occurred (UTC).
    
    Returns:
        A dict with score (0-100), level, and reason.
    """
    known_merchants = ["amazon", "netflix", "stripe", "uber", "github", "apple", "google", "microsoft"]
    
    # Typical bill amounts for velocity check
    typical_bills = {"netflix": 15, "spotify": 10, "github": 4, "amazon": 50}
    
    # Additive scoring (0-100 total)
    # Amount: 0-40 points ($1000+ = 40 max)
    amount_score = min(amount / 125, 40)
    
    # Time: 0-30 points (midnight to 5am is suspicious)
    time_score = 30 if hour in [0, 1, 2, 3, 4, 5] else 0
    
    # Merchant: 0-30 points (unknown merchant is risky)
    merchant_score = 30 if merchant.lower() not in known_merchants else 0
    
    # Anomaly check: amount > 20x typical bill
    typical = typical_bills.get(merchant.lower(), 50)
    anomaly_score = 25 if amount > (typical * 20) else 0
    
    # Total score is sum of components (0-100)
    total_score = amount_score + time_score + merchant_score + anomaly_score
    total_score = round(min(total_score, 100), 1)
    
    # Thresholds: <30 low, 30-60 medium, >60 high
    if total_score < 30:
        level = "low"
    elif total_score <= 60:
        level = "medium"
    else:
        level = "high"
    
    # Build reason string
    reasons = []
    if amount_score >= 8:  # $1000+
        reasons.append("High amount")
    if time_score > 0:
        reasons.append("Suspicious hour")
    if merchant_score > 0:
        reasons.append("Unknown merchant")
    if anomaly_score > 0:
        reasons.append(f"Anomaly: +25pts (amount > 20x typical ${typical})")
    
    reason = " + ".join(reasons) if reasons else "Normal transaction"
    
    return {
        "score": total_score,
        "level": level,
        "reason": reason
    }


@mcp.tool()
async def get_fraud_score(amount: float, merchant: str, hour: int) -> str:
    """
    Get a fraud risk score for a transaction.
    
    Args:
        amount: The transaction amount.
        merchant: The merchant name.
        hour: The hour of the day (0-23) when the transaction occurred.
    
    Returns:
        A formatted string with the risk assessment.
    """
    result = score_transaction(amount, merchant, hour)
    
    return f"""Risk Assessment:
Score: {result['score']}/100
Level: {result['level'].upper()}
Reason: {result['reason']}"""


@mcp.tool()
async def score_payment_risk(amount: float, merchant: str, hour: int) -> str:
    """
    Score the fraud risk of a payment transaction.
    
    Args:
        amount: The transaction amount.
        merchant: The merchant name.
        hour: The hour of the day (0-23) when the transaction occurred.
    
    Returns:
        A user-friendly risk assessment with score, level, and recommendation.
    """
    # Input validation
    if not merchant or not merchant.strip():
        return "Error: Merchant name required"
    if amount <= 0:
        return "Error: Amount must be positive"
    if not isinstance(hour, int) or hour < 0 or hour > 23:
        return "Error: Hour must be UTC (0-23)"
    
    result = score_transaction(amount, merchant.strip(), hour)
    
    # Determine recommendation based on score (matches thresholds)
    if result['score'] < 30:
        recommendation = "Auto-approve"
    elif result['score'] <= 60:
        recommendation = "Review"
    else:
        recommendation = "Block"
    
    return f"""Payment Risk Assessment:
Score: {result['score']}/100
Risk Level: {result['level'].upper()}
Reason: {result['reason']}
Recommendation: {recommendation}"""


@mcp.tool()
async def get_agent_status() -> str:
    """
    Get the current status of all consensus agents.
    
    Returns:
        A formatted string showing agent health status.
    """
    engine = ConsensusEngine()
    
    lines = ["Agent Status Report:"]
    lines.append("=" * 40)
    
    for agent in engine.agents:
        # 90% chance healthy, 10% degraded
        is_healthy = random.random() < 0.9
        status = "HEALTHY" if is_healthy else "DEGRADED"
        status_icon = "[OK]" if is_healthy else "[!]"
        
        lines.append(f"{status_icon} {agent['name']} ({agent['id']})")
        lines.append(f"  Role: {agent['role']}")
        lines.append(f"  Trust Score: {agent['trust_score']}")
        lines.append(f"  Status: {status}")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport='sse', host='0.0.0.0', port=8765)
