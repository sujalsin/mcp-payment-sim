"""Integration test suite for the MCP Payments Simulator.

This module provides a comprehensive set of edge-case tests to verify
input validation, fraud scoring, consensus voting, and agent status tools.
"""

import asyncio
import sys
from typing import Any, Dict, List

from mcp import ClientSession
from mcp.client.sse import sse_client


async def run_validation_tests(session: ClientSession) -> tuple[int, int]:
    """Runs input validation tests.

    Args:
        session: An active ClientSession.

    Returns:
        A tuple of (passed, failed) counts.
    """
    print("\n[TEST 1] Input Validation")
    print("-" * 50)
    passed, failed = 0, 0

    test_cases = [
        ("score_payment_risk", {"amount": 100, "merchant": "", "hour": 10}, "Error: Merchant name required"),
        ("score_payment_risk", {"amount": 100, "merchant": "   ", "hour": 10}, "Error: Merchant name required"),
        ("score_payment_risk", {"amount": -100, "merchant": "Amazon", "hour": 10}, "Error: Amount must be positive"),
        ("score_payment_risk", {"amount": 0, "merchant": "Amazon", "hour": 10}, "Error: Amount must be positive"),
        ("score_payment_risk", {"amount": 100, "merchant": "Amazon", "hour": -1}, "Error: Hour must be UTC (0-23)"),
        ("score_payment_risk", {"amount": 100, "merchant": "Amazon", "hour": 24}, "Error: Hour must be UTC (0-23)"),
    ]

    for tool, args, expected in test_cases:
        result = await session.call_tool(tool, args)
        text = result.content[0].text
        if expected in text:
            passed += 1
            print(f"  [PASS] {args.get('merchant') or 'Empty'} / {args.get('amount')} -> Correct Error")
        else:
            failed += 1
            print(f"  [FAIL] {args} -> Expected '{expected}', got '{text}'")

    return passed, failed


async def run_fraud_tests(session: ClientSession) -> tuple[int, int]:
    """Runs fraud scoring and anomaly detection tests.

    Args:
        session: An active ClientSession.

    Returns:
        A tuple of (passed, failed) counts.
    """
    print("\n[TEST 2] Fraud Scoring & Anomaly Detection")
    print("-" * 50)
    passed, failed = 0, 0

    fraud_tests = [
        (50, "Amazon", 10, "LOW", "Auto-approve"),
        (100, "Netflix", 14, "LOW", "Auto-approve"),
        (500, "Unknown", 14, "MEDIUM", "Review"),
        (1000, "Sketchy", 3, "HIGH", "Block"),
        (750, "Netflix", 10, "MEDIUM", "Anomaly"),
        (100, "Netflix", 10, "LOW", ""),
    ]

    for amt, merch, hr, exp_level, exp_keyword in fraud_tests:
        result = await session.call_tool("score_payment_risk", {"amount": amt, "merchant": merch, "hour": hr})
        text = result.content[0].text
        if exp_level in text and (not exp_keyword or exp_keyword in text):
            passed += 1
            print(f"  [PASS] ${amt} {merch} -> {exp_level}")
        else:
            failed += 1
            print(f"  [FAIL] ${amt} {merch} -> Expected {exp_level} ({exp_keyword}), got {text[:50]}...")

    return passed, failed


async def run_consensus_tests(session: ClientSession) -> tuple[int, int]:
    """Runs consensus voting and agent detail tests.

    Args:
        session: An active ClientSession.

    Returns:
        A tuple of (passed, failed) counts.
    """
    print("\n[TEST 3] Consensus Voting")
    print("-" * 50)
    passed, failed = 0, 0

    consensus_tests = [
        (50, "Amazon", "APPROVED"),
        (500, "Amazon", "APPROVED"),
        (750, "Stripe", "APPROVED"),
        (1001, "Netflix", "REJECTED"),
        (10001, "Amazon", "REJECTED"),
    ]

    for amt, merch, expected in consensus_tests:
        result = await session.call_tool("execute_with_consensus", {"amount": amt, "merchant": merch})
        text = result.content[0].text
        if f"Status: {expected}" in text and "Agents:" in text:
            passed += 1
            print(f"  [PASS] ${amt} {merch} -> {expected}")
        else:
            failed += 1
            print(f"  [FAIL] ${amt} {merch} -> Expected {expected}, got {text[:50]}...")

    return passed, failed


async def run_operational_tests(session: ClientSession) -> tuple[int, int]:
    """Runs tests for operational tools like cards, receipts, and status.

    Args:
        session: An active ClientSession.

    Returns:
        A tuple of (passed, failed) counts.
    """
    print("\n[TEST 4] Operational Tools")
    print("-" * 50)
    passed, failed = 0, 0

    # Card Creation
    result = await session.call_tool("create_merchant_locked_card", {"merchant": "Amazon", "amount": 100})
    if "Card created" in result.content[0].text:
        passed += 1
        print("  [PASS] Card creation")
    else:
        failed += 1
        print("  [FAIL] Card creation")

    # Receipts
    result = await session.call_tool("get_receipts", {"customer_email": "test@example.com", "days": 7})
    if "Receipts for test@example.com" in result.content[0].text:
        passed += 1
        print("  [PASS] Receipt generation")
    else:
        failed += 1
        print("  [FAIL] Receipt generation")

    # Agent Status
    result = await session.call_tool("get_agent_status", {})
    if "Agent Status Report" in result.content[0].text:
        passed += 1
        print("  [PASS] Agent status report")
    else:
        failed += 1
        print("  [FAIL] Agent status report")

    return passed, failed


async def run_all_tests():
    """Orchestrates the execution of all test suites."""
    print("=" * 70)
    print("MCP PAYMENTS SIMULATOR: INTEGRATION TEST SUITE")
    print("=" * 70)

    try:
        async with sse_client("http://localhost:8765/sse") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                v_passed, v_failed = await run_validation_tests(session)
                f_passed, f_failed = await run_fraud_tests(session)
                c_passed, c_failed = await run_consensus_tests(session)
                o_passed, o_failed = await run_operational_tests(session)

                total_passed = v_passed + f_passed + c_passed + o_passed
                total_failed = v_failed + f_failed + c_failed + o_failed

                print("\n" + "=" * 70)
                print(f"FINAL RESULTS: {total_passed} Passed, {total_failed} Failed")
                print("=" * 70)

                if total_failed == 0:
                    print("\nSUCCESS: All integration tests passed.")
                    sys.exit(0)
                else:
                    print(f"\nFAILURE: {total_failed} tests failed.")
                    sys.exit(1)

    except Exception as e:
        print(f"\nERROR: Could not connect to server or test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
