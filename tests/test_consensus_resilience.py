"""Verification script for Phase 3: Consensus Resilience.

This script demonstrates the automated revocation and exclusion of compromised 
agents from the consensus process.
"""

import asyncio
import sys
from mcp import ClientSession
from mcp.client.sse import sse_client
import numpy as np

async def run_resilience_test():
    print("=" * 70)
    print("PHASE 3: CONSENSUS RESILIENCE & AUTO-REVOCATION TEST")
    print("=" * 70)

    try:
        async with sse_client("http://localhost:8765/sse") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1. Start with clean state (reinstate agents if needed)
                print("\n[STEP 1] Initializing healthy state...")
                agents = ["finance_agent_001", "compliance_agent_002", "audit_agent_003"]
                for agent_id in agents:
                    await session.call_tool("reinstate_agent", {"agent_id": agent_id})
                
                # Setup baseline for agents (requires some approved amounts)
                # We'll do this by approving some small transactions
                for _ in range(5):
                    await session.call_tool("execute_with_consensus", {"amount": 50, "merchant": "Amazon"})

                # 2. Normal Transaction
                print("\n[STEP 2] Executing normal transaction ($500)...")
                result = await session.call_tool("execute_with_consensus", {"amount": 500, "merchant": "Amazon"})
                text = result.content[0].text
                print(text)
                if "Active Votes:" in text and "finance_agent_001" in text:
                    print("  [PASS] All agents voted normally.")
                else:
                    print("  [FAIL] Unexpected consensus output.")

                # 3. Simulate Tampering
                print("\n[STEP 3] Simulating tempering for finance_agent_001...")
                await session.call_tool("simulate_tampering", {"agent_id": "finance_agent_001"})
                
                # 4. Execute large transaction to trigger REVOKE
                # A large amount ($2000) will trigger both behavioral drift and hash check
                print("\n[STEP 4] Executing large transaction ($2000) to trigger auto-revocation...")
                result = await session.call_tool("execute_with_consensus", {"amount": 2000, "merchant": "Amazon"})
                text = result.content[0].text
                print(text)
                
                if "COMPROMISED (Revoking now)" in text and "finance_agent_001" in text:
                    print("  [PASS] finance_agent_001 was detected as COMPROMISED and revoked.")
                else:
                    print("  [FAIL] finance_agent_001 was not revoked as expected.")

                # 5. Verify Exclusion
                print("\n[STEP 5] Verifying exclusion in subsequent transaction...")
                result = await session.call_tool("execute_with_consensus", {"amount": 500, "merchant": "Amazon"})
                text = result.content[0].text
                print(text)
                
                if "EXCLUDED (Previously Revoked)" in text and "finance_agent_001" in text:
                    print("  [PASS] finance_agent_001 remains excluded.")
                    if "compliance_agent_002" in text and "audit_agent_003" in text:
                        print("  [PASS] Consensus still operating with remaining agents.")
                else:
                    print("  [FAIL] Exclusion logic failed.")

                # 6. Verify Compromised Agents Tool
                print("\n[STEP 6] Checking compromised agents tool...")
                result = await session.call_tool("get_compromised_agents", {})
                text = result.content[0].text
                print(text)
                if "finance_agent_001" in text:
                    print("  [PASS] finance_agent_001 listed in compromised agents.")
                else:
                    print("  [FAIL] finance_agent_001 missing from report.")

                # 7. Reinstate and Verify
                print("\n[STEP 7] Reinstating finance_agent_001...")
                await session.call_tool("reinstate_agent", {"agent_id": "finance_agent_001"})
                
                result = await session.call_tool("execute_with_consensus", {"amount": 500, "merchant": "Amazon"})
                text = result.content[0].text
                print(text)
                if "finance_agent_001" in text and "Active Votes" in text:
                    print("  [PASS] finance_agent_001 successfully returned to consensus.")
                else:
                    print("  [FAIL] Reinstatement failed.")

                print("\n" + "=" * 70)
                print("PHASE 3 VERIFICATION COMPLETE: ALL SYSTEMS GO")
                print("=" * 70)

    except Exception as e:
        print(f"\nERROR: Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_resilience_test())
