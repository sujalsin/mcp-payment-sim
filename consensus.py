import json
from pathlib import Path


class ConsensusEngine:
    """Engine for simulating multi-agent consensus voting on transactions."""
    
    def __init__(self, threshold: float = 0.67):
        """
        Initialize the ConsensusEngine.
        
        Args:
            threshold: Minimum approval rate required for consensus (default 0.67 = 67%)
        """
        self.threshold = threshold
        self.agents = []
        self.load_agents()
    
    def load_agents(self) -> None:
        """Load agents from agents.json file."""
        agents_file = Path(__file__).parent / "agents.json"
        with open(agents_file, "r") as f:
            data = json.load(f)
            self.agents = data.get("agents", [])
    
    def simulate_vote(self, amount: float, merchant: str) -> dict:
        """
        Simulate a voting process where each agent votes on a transaction.
        
        Args:
            amount: The transaction amount to vote on.
            merchant: The merchant name for the transaction.
        
        Returns:
            A dict with status, votes list, and approval_rate.
        """
        known_merchants = ["amazon", "netflix", "stripe", "uber", "github"]
        votes = []
        
        for agent in self.agents:
            # Finance Agent: Approves anything under $10k
            if "finance" in agent['id']:
                vote = "approve" if amount <= 10000 else "reject"
                
            # Compliance Agent: Reviews unknown merchants
            elif "compliance" in agent['id']:
                vote = "review" if merchant.lower() not in known_merchants else "approve"
                
            # Audit Agent: Reviews amounts over $500
            elif "audit" in agent['id']:
                vote = "review" if amount > 500 else "approve"
            else:
                vote = "approve"
            
            votes.append({
                "agent_id": agent['id'],
                "vote": vote,
                "reason": f"Amount ${amount}, merchant {merchant}"
            })
        
        # Determine required threshold based on amount
        if amount <= 100:
            required_threshold = 0.0  # Auto-approve
        elif amount <= 1000:
            required_threshold = 0.67  # 67% for medium amounts
        else:
            required_threshold = 0.80  # 80% for high amounts
        
        # Count approvals (treat "review" as "reject")
        approve_count = sum(1 for v in votes if v['vote'] == 'approve')
        total_votes = len(votes)
        approval_rate = approve_count / total_votes
        
        # FIX: Round to avoid floating-point bugs
        if round(approval_rate, 2) >= round(required_threshold, 2):
            status = "approved"
        else:
            status = "rejected"
        
        return {
            "transaction_id": f"tx_{hash(merchant + str(amount))}"[:10],
            "status": status,
            "votes": votes,
            "approval_rate": round(approval_rate, 2),
            "required_threshold": required_threshold
        }


if __name__ == "__main__":
    # Quick test
    engine = ConsensusEngine()
    
    print("Test 1: $100 transaction")
    result = engine.simulate_vote(100.0, "Amazon")
    print(f"Status: {result['status']}, Approval Rate: {result['approval_rate']}")
    
    print("\nTest 2: $6000 transaction")
    result = engine.simulate_vote(6000.0, "Stripe")
    print(f"Status: {result['status']}, Approval Rate: {result['approval_rate']}")
    
    print("\nTest 3: $15000 transaction")
    result = engine.simulate_vote(15000.0, "GitHub")
    print(f"Status: {result['status']}, Approval Rate: {result['approval_rate']}")