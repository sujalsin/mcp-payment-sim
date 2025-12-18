# MCP Payments Simulator

Built to prototype agentic payment infrastructure with multi-agent consensus and fraud scoring.

## Architecture

- **MCP Server**: 7 tools accessible via Claude
- **Consensus Engine**: 3-agent Byzantine voting (67%/80% threshold based on amount)
- **Fraud Detection**: Rule-based scoring (amount/time/merchant/anomaly)
- **Storage**: SQLite for mandates and transactions

## Quick Start

```bash
pip install mcp fastmcp
python main.py
```

Server runs on `http://0.0.0.0:8765/sse`

## Tools

| Tool | Description |
|------|-------------|
| `create_merchant_locked_card` | Create a virtual card locked to a specific merchant |
| `get_receipts` | Generate fake receipts for a customer email |
| `execute_with_consensus` | Execute a transaction with multi-agent voting |
| `get_fraud_score` | Get basic fraud risk score |
| `score_payment_risk` | Detailed risk assessment with recommendation |
| `get_agent_status` | Check health status of consensus agents |

## Fraud Scoring

```
Score = Amount (0-40) + Time (0-30) + Merchant (0-30) + Anomaly (0-25)
```

| Range | Level | Recommendation |
|-------|-------|----------------|
| < 30 | LOW | Auto-approve |
| 30-60 | MEDIUM | Manual review |
| > 60 | HIGH | Block |

### Anomaly Detection
If amount > 20x typical bill for merchant, +25 points added.

## Consensus Voting

| Amount | Threshold | Agents Required |
|--------|-----------|-----------------|
| < $100 | Auto-approve | None |
| $100-$1000 | 67% | 2 of 3 |
| > $1000 | 80% | 3 of 3 |

### Agents

| Agent | Role | Voting Rule |
|-------|------|-------------|
| Finance Agent | Primary Approver | Approves if ≤ $10,000 |
| Compliance Agent | Secondary Approver | Reviews unknown merchants |
| Audit Agent | Reviewer | Reviews amounts > $500 |

## Files

```
├── main.py           # MCP server with all tools
├── consensus.py      # ConsensusEngine class
├── agents.json       # Agent configuration
├── payments.db       # SQLite database
└── test_server.py    # Comprehensive test suite
```

## Testing

```bash
# Start server
python main.py

# Run tests (in another terminal)
python test_server.py
```

## License

MIT
