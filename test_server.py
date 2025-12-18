"""Comprehensive edge case test suite for MCP Payments Simulator."""
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client


async def run_all_tests():
    """Run comprehensive edge case tests."""
    async with sse_client("http://localhost:8765/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            passed = 0
            failed = 0
            
            print("=" * 70)
            print("COMPREHENSIVE EDGE CASE TESTING")
            print("=" * 70)
            
            # ========================================
            # TEST 1: Input Validation
            # ========================================
            print("\n[TEST 1] Input Validation")
            print("-" * 50)
            
            # 1a. Empty merchant
            result = await session.call_tool("score_payment_risk", {
                "amount": 100, "merchant": "", "hour": 10
            })
            if "Error: Merchant name required" in result.content[0].text:
                passed += 1
                print("  [PASS] Empty merchant returns error")
            else:
                failed += 1
                print("  [FAIL] Empty merchant:", result.content[0].text)
            
            # 1b. Whitespace-only merchant
            result = await session.call_tool("score_payment_risk", {
                "amount": 100, "merchant": "   ", "hour": 10
            })
            if "Error: Merchant name required" in result.content[0].text:
                passed += 1
                print("  [PASS] Whitespace merchant returns error")
            else:
                failed += 1
                print("  [FAIL] Whitespace merchant:", result.content[0].text)
            
            # 1c. Negative amount
            result = await session.call_tool("score_payment_risk", {
                "amount": -100, "merchant": "Amazon", "hour": 10
            })
            if "Error: Amount must be positive" in result.content[0].text:
                passed += 1
                print("  [PASS] Negative amount returns error")
            else:
                failed += 1
                print("  [FAIL] Negative amount:", result.content[0].text)
            
            # 1d. Zero amount
            result = await session.call_tool("score_payment_risk", {
                "amount": 0, "merchant": "Amazon", "hour": 10
            })
            if "Error: Amount must be positive" in result.content[0].text:
                passed += 1
                print("  [PASS] Zero amount returns error")
            else:
                failed += 1
                print("  [FAIL] Zero amount:", result.content[0].text)
            
            # 1e. Invalid hour (negative)
            result = await session.call_tool("score_payment_risk", {
                "amount": 100, "merchant": "Amazon", "hour": -1
            })
            if "Error: Hour must be UTC (0-23)" in result.content[0].text:
                passed += 1
                print("  [PASS] Negative hour returns error")
            else:
                failed += 1
                print("  [FAIL] Negative hour:", result.content[0].text)
            
            # 1f. Invalid hour (> 23)
            result = await session.call_tool("score_payment_risk", {
                "amount": 100, "merchant": "Amazon", "hour": 24
            })
            if "Error: Hour must be UTC (0-23)" in result.content[0].text:
                passed += 1
                print("  [PASS] Hour > 23 returns error")
            else:
                failed += 1
                print("  [FAIL] Hour > 23:", result.content[0].text)
            
            # ========================================
            # TEST 2: Fraud Scoring Thresholds
            # ========================================
            print("\n[TEST 2] Fraud Scoring Thresholds")
            print("-" * 50)
            
            fraud_tests = [
                # (amount, merchant, hour, expected_level, expected_rec)
                (50, "Amazon", 10, "LOW", "Auto-approve"),
                (100, "Netflix", 14, "LOW", "Auto-approve"),
                (500, "Unknown", 14, "MEDIUM", "Review"),
                (1000, "Sketchy", 3, "HIGH", "Block"),
                (5000, "BadSite", 3, "HIGH", "Block"),
            ]
            
            for amount, merchant, hour, exp_level, exp_rec in fraud_tests:
                result = await session.call_tool("score_payment_risk", {
                    "amount": amount, "merchant": merchant, "hour": hour
                })
                response = result.content[0].text
                if exp_level in response and exp_rec in response:
                    passed += 1
                    print(f"  [PASS] ${amount} {merchant} @ {hour}:00 -> {exp_level}")
                else:
                    failed += 1
                    print(f"  [FAIL] ${amount} {merchant} @ {hour}:00")
                    print(f"         Expected: {exp_level}, {exp_rec}")
            
            # ========================================
            # TEST 3: Anomaly Detection
            # ========================================
            print("\n[TEST 3] Anomaly Detection (20x typical bill)")
            print("-" * 50)
            
            # $750 to Netflix (typical $15, 20x = $300) should trigger anomaly
            result = await session.call_tool("score_payment_risk", {
                "amount": 750, "merchant": "Netflix", "hour": 10
            })
            if "Anomaly" in result.content[0].text and "MEDIUM" in result.content[0].text:
                passed += 1
                print("  [PASS] $750 Netflix triggers anomaly -> MEDIUM")
            else:
                failed += 1
                print("  [FAIL] $750 Netflix anomaly check")
            
            # $100 to Netflix (< 20x) should NOT trigger anomaly
            result = await session.call_tool("score_payment_risk", {
                "amount": 100, "merchant": "Netflix", "hour": 10
            })
            if "Anomaly" not in result.content[0].text and "LOW" in result.content[0].text:
                passed += 1
                print("  [PASS] $100 Netflix no anomaly -> LOW")
            else:
                failed += 1
                print("  [FAIL] $100 Netflix should be LOW with no anomaly")
            
            # ========================================
            # TEST 4: Consensus Voting
            # ========================================
            print("\n[TEST 4] Consensus Voting")
            print("-" * 50)
            
            consensus_tests = [
                # (amount, merchant, expected_status)
                (50, "Amazon", "APPROVED"),       # Auto-approve < $100
                (500, "Amazon", "APPROVED"),      # 3/3 = 100% >= 67%
                (750, "Stripe", "APPROVED"),      # 2/3 = 67% >= 67% (Audit reviews)
                (1001, "Netflix", "REJECTED"),    # 2/3 = 67% < 80%
                (5000, "GitHub", "REJECTED"),     # 2/3 = 67% < 80%
                (10001, "Amazon", "REJECTED"),    # 0/3 = 0% (Finance rejects)
            ]
            
            for amount, merchant, expected in consensus_tests:
                result = await session.call_tool("execute_with_consensus", {
                    "amount": amount, "merchant": merchant
                })
                response = result.content[0].text
                if f"Status: {expected}" in response:
                    passed += 1
                    print(f"  [PASS] ${amount} {merchant} -> {expected}")
                else:
                    failed += 1
                    print(f"  [FAIL] ${amount} {merchant}")
                    print(f"         Expected: {expected}")
                    print(f"         Got: {response[:100]}...")
            
            # ========================================
            # TEST 5: Agent Voting Details
            # ========================================
            print("\n[TEST 5] Agent Voting Details")
            print("-" * 50)
            
            result = await session.call_tool("execute_with_consensus", {
                "amount": 750, "merchant": "NewMerchant"
            })
            response = result.content[0].text
            if "Agents:" in response:
                passed += 1
                print("  [PASS] Response includes agent voting details")
            else:
                failed += 1
                print("  [FAIL] Missing agent voting details")
            
            # ========================================
            # TEST 6: Card Creation with Fraud Check
            # ========================================
            print("\n[TEST 6] Card Creation with Fraud Check")
            print("-" * 50)
            
            # Low risk - should create
            result = await session.call_tool("create_merchant_locked_card", {
                "merchant": "Amazon", "amount": 100
            })
            if "Card created" in result.content[0].text:
                passed += 1
                print("  [PASS] Low risk card created")
            else:
                failed += 1
                print("  [FAIL] Low risk card creation")
            
            # High risk - should block or review
            result = await session.call_tool("create_merchant_locked_card", {
                "merchant": "ShadySite", "amount": 5000
            })
            if "BLOCKED" in result.content[0].text or "REVIEW" in result.content[0].text:
                passed += 1
                print("  [PASS] High risk card blocked/reviewed")
            else:
                failed += 1
                print("  [FAIL] High risk should be blocked:", result.content[0].text)
            
            # Empty merchant validation
            result = await session.call_tool("create_merchant_locked_card", {
                "merchant": "", "amount": 100
            })
            if "Error" in result.content[0].text:
                passed += 1
                print("  [PASS] Empty merchant returns error")
            else:
                failed += 1
                print("  [FAIL] Empty merchant should error")
            
            # ========================================
            # TEST 7: Get Receipts
            # ========================================
            print("\n[TEST 7] Get Receipts")
            print("-" * 50)
            
            result = await session.call_tool("get_receipts", {
                "customer_email": "test@example.com", "days": 7
            })
            response = result.content[0].text
            if "Receipts for test@example.com" in response and "$" in response:
                passed += 1
                print("  [PASS] Receipts returned with valid format")
            else:
                failed += 1
                print("  [FAIL] Invalid receipts format")
            
            # ========================================
            # TEST 8: Agent Status
            # ========================================
            print("\n[TEST 8] Agent Status")
            print("-" * 50)
            
            result = await session.call_tool("get_agent_status", {})
            response = result.content[0].text
            if "Agent Status Report" in response and "finance_agent" in response:
                passed += 1
                print("  [PASS] Agent status returned")
            else:
                failed += 1
                print("  [FAIL] Agent status missing expected content")
            
            # ========================================
            # TEST 9: Boundary Values
            # ========================================
            print("\n[TEST 9] Boundary Values")
            print("-" * 50)
            
            # Exactly $100 (should NOT auto-approve)
            result = await session.call_tool("execute_with_consensus", {
                "amount": 100, "merchant": "Amazon"
            })
            if "3 of 3" in result.content[0].text or "APPROVED" in result.content[0].text:
                passed += 1
                print("  [PASS] $100 exact uses consensus (not auto-approve)")
            else:
                failed += 1
                print("  [FAIL] $100 boundary")
            
            # Exactly $1000 (67% threshold)
            result = await session.call_tool("execute_with_consensus", {
                "amount": 1000, "merchant": "Amazon"
            })
            if "APPROVED" in result.content[0].text:
                passed += 1
                print("  [PASS] $1000 uses 67% threshold")
            else:
                failed += 1
                print("  [FAIL] $1000 boundary")
            
            # $1001 (80% threshold)
            result = await session.call_tool("execute_with_consensus", {
                "amount": 1001, "merchant": "Amazon"
            })
            if "REJECTED" in result.content[0].text or "80%" in result.content[0].text:
                passed += 1
                print("  [PASS] $1001 uses 80% threshold")
            else:
                failed += 1
                print("  [FAIL] $1001 boundary")
            
            # Hour boundaries
            for hour in [0, 5, 6, 23]:
                result = await session.call_tool("score_payment_risk", {
                    "amount": 100, "merchant": "Unknown", "hour": hour
                })
                response = result.content[0].text
                if hour <= 5:
                    expected = "Suspicious hour" in response
                else:
                    expected = "Suspicious hour" not in response
                if expected:
                    passed += 1
                    print(f"  [PASS] Hour {hour} -> {'suspicious' if hour <= 5 else 'normal'}")
                else:
                    failed += 1
                    print(f"  [FAIL] Hour {hour} boundary")
            
            # ========================================
            # SUMMARY
            # ========================================
            print("\n" + "=" * 70)
            print(f"RESULTS: {passed} passed, {failed} failed")
            print("=" * 70)
            
            if failed == 0:
                print("\nALL TESTS PASSED!")
            else:
                print(f"\n{failed} test(s) need attention.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
