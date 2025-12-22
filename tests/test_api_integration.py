"""API Integration Test: Full Production Flow.

This script verifies the end-to-end flow of the MCP Payments Simulator, 
including establishing a baseline, detecting tampering, auto-revocation, 
and manual reinstatement.
"""

import asyncio
import sys
import sqlite3
from mcp import ClientSession
from mcp.client.sse import sse_client

async def test_full_production_flow():
    """
    End-to-end test: consensus + detection + revocation + reinstatement
    """
    print("=" * 70)
    print("FULL PRODUCTION FLOW INTEGRATION TEST")
    print("=" * 70)

    try:
        async with sse_client("http://localhost:8765/sse") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1. Clean slate
                print("\n[STEP 1] Cleaning database state...")
                conn = sqlite3.connect("payments.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM agent_behavior")
                cursor.execute("DELETE FROM revoked_agents")
                conn.commit()
                conn.close()
                print("  Database state reset.")

                # 2. Establish baseline
                print("\n[STEP 2] Establishing behavioral baseline (10 transactions)...")
                for i in range(10):
                    await session.call_tool("execute_with_consensus", {"amount": 100, "merchant": "test"})
                print("  Baseline established.")

                # 3. Tamper one agent
                # Using official project ID: finance_agent_001
                print("\n[STEP 3] Tampering finance_agent_001 model weights...")
                await session.call_tool("simulate_tampering", {"agent_id": "finance_agent_001"})

                # 4. Execute transaction requiring consensus
                # $600 triggers behavioral anomaly (drift from $100 baseline)
                # Combined with tampering, this triggers REVOKE
                print("\n[STEP 4] Executing consensus transaction ($600)...")
                result = await session.call_tool("execute_with_consensus", {"amount": 600, "merchant": "test"})
                text = result.content[0].text
                print(f"\nExecution Report:\n{text}")

                # 5. Verify: finance_agent_001 should be excluded/compromised
                print("\n[STEP 5] Verifying integrity actions...")
                
                # Check exclusion in report
                assert "finance_agent_001: COMPROMISED" in text
                assert "compliance_agent_002" in text
                assert "audit_agent_003" in text
                
                # Verify it's in the compromised agents list
                comp_result = await session.call_tool("get_compromised_agents", {})
                comp_text = comp_result.content[0].text
                assert "finance_agent_001" in comp_text
                print("  [PASS] Compromised agent detected and revoked.")

                # 6. Reinstate after audit
                print("\n[STEP 6] Reinstating finance_agent_001 after audit...")
                await session.call_tool("reinstate_agent", {"agent_id": "finance_agent_001"})
                
                # Verify removal from compromised list
                comp_result = await session.call_tool("get_compromised_agents", {})
                comp_text = comp_result.content[0].text
                assert "finance_agent_001" not in comp_text
                print("  [PASS] Agent reinstated successfully.")

                print("\n" + "=" * 70)
                print("FULL PRODUCTION FLOW VERIFIED")
                print("=" * 70)

    except Exception as e:
        print(f"\nERROR: Full production flow test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_full_production_flow())
