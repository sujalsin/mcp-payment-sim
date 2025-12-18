# MCP Payments Architecture

## Layer 1: MCP Interface
- 4 tools:
  1. create_merchant_locked_card(merchant, amount)
  2. get_transaction_history(customer_email)
  3. execute_with_consensus(amount, merchant)
  4. get_fraud_score(amount, merchant, hour)

## Layer 2: Fake Data Engine
- Receipt generator: random amounts ($5-$500), merchants, dates
- Mandate storage: SQLite with mandates table
- Agent registry: agents.json with trust scores

## Layer 3: Consensus Engine
- 3 agents vote: Finance, Compliance, Audit
- Voting rules:
  - Amount < $100: auto-approve
  - Amount $100-$1000: agent vote
  - Amount > $1000: require 80% approval
- Threshold: 67% (2/3 agents)

## Layer 4: Fraud Scoring
- Features: amount_percentile, time_anomaly, merchant_reputation
- Weights: 0.4, 0.3, 0.3
- Output: 0-100 score, threshold at 70