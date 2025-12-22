"""Module for simulating multi-agent consensus voting on transactions.

This module provides the logic for different agents (Finance, Compliance, Audit)
to evaluate and vote on transactions based on specific business rules.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, TypedDict


class Vote(TypedDict):
    """Type definition for an agent's individual vote on a transaction.

    Attributes:
        agent_id: The unique identifier for the voting agent.
        vote: The agent's decision ('approve', 'reject', or 'review').
        reason: Justification for the voting decision.
    """
    agent_id: str
    vote: str
    reason: str


class ConsensusResult(TypedDict):
    """Type definition for the result of a multi-agent consensus simulation.

    Attributes:
        transaction_id: Unique identifier for the transaction.
        status: Final consensus outcome ('approved' or 'rejected').
        votes: A list of individual votes from each participant.
        approval_rate: Percentage of agents that approved (0.0 to 1.0).
        required_threshold: Minimum rate required for approval.
    """
    transaction_id: str
    status: str
    votes: List[Vote]
    approval_rate: float
    required_threshold: float


class ConsensusEngine:
    """Engine for simulating multi-agent consensus voting on transactions.
    
    This engine loads multiple agent profiles and evaluates transactions
    against their specific rules to determine if a transaction should be
    approved, rejected, or sent for review.
    """

    def __init__(self, threshold: float = 0.67):
        """Initializes the ConsensusEngine with a default majority threshold.

        Args:
            threshold: Minimum approval rate required for consensus. Defaults to 0.67.
        """
        self.threshold = threshold
        self.agents: List[Dict[str, Any]] = []
        self._load_agents()

    def _load_agents(self) -> None:
        """Loads agent configurations from the local agents.json file.

        Raises:
            FileNotFoundError: If agents.json is missing.
            json.JSONDecodeError: If agents.json is malformed.
        """
        agents_file = Path(__file__).parent / "agents.json"
        try:
            with open(agents_file, "r") as f:
                data = json.load(f)
                self.agents = data.get("agents", [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # In a production environment, we'd use proper logging here.
            print(f"Error loading agents: {e}")
            self.agents = []

    def simulate_vote(self, amount: float, merchant: str) -> ConsensusResult:
        """Simulates a multi-agent voting process for a specific transaction.

        Args:
            amount: The transaction amount to be evaluated.
            merchant: The name of the merchant involved in the transaction.

        Returns:
            A ConsensusResult object specifying the outcome and voting details.
        """
        known_merchants = {"amazon", "netflix", "stripe", "uber", "github"}
        votes: List[Vote] = []

        for agent in self.agents:
            agent_id = agent["id"]
            
            # Implementation of agent-specific business logic.
            if "finance" in agent_id:
                # Finance Agent: Approves anything under $10,000.
                vote_decision = "approve" if amount <= 10000 else "reject"
            elif "compliance" in agent_id:
                # Compliance Agent: Reviews unknown merchants.
                vote_decision = "review" if merchant.lower() not in known_merchants else "approve"
            elif "audit" in agent_id:
                # Audit Agent: Reviews high-value transactions.
                vote_decision = "review" if amount > 500 else "approve"
            else:
                vote_decision = "approve"

            votes.append({
                "agent_id": agent_id,
                "vote": vote_decision,
                "reason": f"Evaluated amount ${amount:.2f} for merchant {merchant}"
            })

        # Determine the dynamic required threshold based on risk (amount).
        if amount <= 100:
            required_threshold = 0.0  # Auto-approve small amounts.
        elif amount <= 1000:
            required_threshold = 0.67  # Standard 2/3 majority.
        else:
            required_threshold = 0.80  # Supermajority for large amounts.

        # Calculate the approval rate (treating 'review' and 'reject' as non-approvals).
        approved_count = sum(1 for v in votes if v["vote"] == "approve")
        total_votes = len(votes)
        approval_rate = approved_count / total_votes if total_votes > 0 else 0.0

        # Consensus comparison using rounded precision.
        # This ensures that a 2/3 majority (0.666...) satisfies a 67% threshold.
        is_approved = round(approval_rate, 2) >= required_threshold
        status = "approved" if is_approved else "rejected"

        # Unique transaction identifier for tracking.
        tx_id_raw = f"{merchant}_{amount}_{len(votes)}"
        tx_id = f"tx_{hash(tx_id_raw) % 10**8:08d}"

        return {
            "transaction_id": tx_id,
            "status": status,
            "votes": votes,
            "approval_rate": round(approval_rate, 2),
            "required_threshold": required_threshold
        }