# MCP Payments Simulator

A high-fidelity prototype of agentic payment infrastructure, featuring multi-agent consensus voting, behavioral fingerprinting, and risk-based fraud scoring.

## Overview

The **MCP Payments Simulator** is designed to demonstrate robust, multi-agent evaluation of financial transactions. It utilizes the Model Context Protocol (MCP) to expose a suite of tools for transaction execution, risk assessment, and behavioral monitoring.

## System Architecture

### 1. Model Context Protocol (MCP) Tier
Exposes 7 professional tools for lifecycle management of virtual cards, transaction history retrieval, and consensus-driven execution.

### 2. Multi-Agent Consensus Tier
Implements a Byzantine-resistant voting mechanism using three specialized agents:
- **Finance Agent**: Primary approver for liquidity and budget adherence.
- **Compliance Agent**: Secondary approver for merchant reputation and regulatory checks.
- **Audit Agent**: Specialized reviewer for high-value or unusual patterns.

**Voting Logic:**
- **Auto-approve**: Transactions < $100.
- **Standard Majority (2/3)**: Transactions $100 - $1,000.
- **Supermajority (3/3)**: Transactions > $1,000.

### 3. Behavioral Fingerprinting (Layer 4)
Maintains a 2-sigma behavioral baseline for agents. If an agent's voting behavior (amount approved) drifts more than two standard deviations from their historical mean, they are flagged for revocation.

### 4. Fraud Scoring Engine
A multi-dimensional scoring algorithm (0-100) based on:
- **Velocity & Amount**: Transaction size relative to limits.
- **Temporal Analysis**: UTC hour assessment (high risk during late-night hours).
- **Merchant Reputation**: Validation against known healthy merchants.
- **Anomaly Detection**: 20x deviation from typical merchant bill size.

## Project Structure

```text
├── main.py           # MCP Server & Tool Definitions
├── database.py       # Modular SQLite Persistence Layer
├── consensus.py      # Multi-Agent Voting Engine
├── agents.json       # Agent Profiles & Metadata
├── test_server.py    # Integration Test Suite (32+ Edge Cases)
├── test_behavioral.py # Behavioral Logic Verification
└── tests/            # Visualization & Phase Analysis
```

## Setup & Operation

### Prerequisites
- Python 3.10+
- `mcp` (FastMCP framework)

### Quick Start
```bash
# Install dependencies
pip install mcp fastmcp

# Start the simulation server
python main.py
```

### Verification
```bash
# Run the integration test suite
python test_server.py

# Run the behavioral analysis suite
python test_behavioral.py
```

## Technical Standards
This project adheres to senior engineering standards, including:
- **Modularity**: Strict separation of concerns between storage, logic, and interface.
- **Type Safety**: Comprehensive PEP 484 type hinting.
- **Documentation**: Google-style docstrings for all public and private entities.
- **Persistence**: Safe SQLite connection management via context managers.

## License
MIT
