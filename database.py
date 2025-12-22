"""Module for handling database persistence and schema management.

This module encapsulates all interactions with the SQLite database, providing
a clean interface for the application and ensuring proper connection management.
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List


class DatabaseManager:
    """Manages SQLite database connections and operations."""

    def __init__(self, db_path: str = "payments.db"):
        """Initializes the DatabaseManager with a specific database file.

        Args:
            db_path: Path to the SQLite database file. Defaults to "payments.db".
        """
        self.db_path = Path(db_path)
        self._local = threading.local()
        self._initialize_schema()

    @contextmanager
    def _get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager to provide a database cursor with automatic cleanup.

        Yields:
            A sqlite3.Cursor object for executing database commands.

        Raises:
            RuntimeError: If a database error occurs during operation.
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise RuntimeError(f"Database error: {e}") from e
        finally:
            conn.close()

    def _initialize_schema(self) -> None:
        """Initializes the database schema if it doesn't already exist."""
        with self._get_cursor() as cursor:
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

            # Create agent_behavior table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_behavior (
                    agent_id TEXT,
                    transaction_id TEXT,
                    vote TEXT,
                    amount REAL,
                    timestamp TIMESTAMP,
                    PRIMARY KEY (agent_id, transaction_id)
                )
            """)

            # Create revoked_agents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS revoked_agents (
                    agent_id TEXT PRIMARY KEY,
                    reason TEXT,
                    revoked_at TIMESTAMP
                )
            """)

    def create_mandate(self, mandate_id: str, card_number: str, 
                       amount: float, merchant: str) -> None:
        """Registers a new merchant-locked mandate.

        Args:
            mandate_id: Unique identifier for the mandate.
            card_number: The generated virtual card number.
            amount: Spending limit for the mandate.
            merchant: Name of the merchant the card is locked to.
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO mandates (id, agent_id, amount, merchant, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (mandate_id, card_number, amount, merchant, 
                 datetime.now().isoformat())
            )

    def log_transaction(self, tx_id: str, amount: float, merchant: str, 
                        status: str) -> None:
        """Logs a completed transaction to the database.

        Args:
            tx_id: Unique identifier for the transaction.
            amount: The transaction amount.
            merchant: The merchant name.
            status: Final status (e.g., 'approved', 'rejected').
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO transactions (id, amount, merchant, status, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (tx_id, amount, merchant, status, datetime.now().isoformat())
            )

    def log_agent_vote(self, agent_id: str, tx_id: str, vote: str, 
                       amount: float) -> None:
        """Logs an individual agent's vote for a transaction.

        Args:
            agent_id: Identifier of the voting agent.
            tx_id: Transaction identifier.
            vote: The agent's decision (e.g., 'APPROVE', 'REJECT').
            amount: The transaction amount.
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO agent_behavior (agent_id, transaction_id, vote, amount, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (agent_id, tx_id, vote.upper(), amount, 
                 datetime.now().isoformat())
            )

    def get_agent_approved_amounts(self, agent_id: str) -> List[float]:
        """Retrieves all amounts approved by a specific agent.

        Args:
            agent_id: The unique identifier for the agent.

        Returns:
            A list of transaction amounts that the agent has approved.
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT amount FROM agent_behavior WHERE agent_id = ? "
                "AND vote = 'APPROVE'",
                (agent_id,)
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows]

    def get_recent_approved_amounts(self, agent_id: str, limit: int = 100) -> List[float]:
        """Retrieves recent approved amounts for an agent, ordered by recency.

        Args:
            agent_id: The agent's identifier.
            limit: Maximum number of records to retrieve.

        Returns:
            A list of amounts, ordered most recent first.
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT amount FROM agent_behavior WHERE agent_id = ? "
                "AND vote = 'APPROVE' ORDER BY timestamp DESC LIMIT ?",
                (agent_id, limit)
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows]

    def revoke_agent(self, agent_id: str, reason: str) -> None:
        """Marks an agent as revoked in the database.

        Args:
            agent_id: The unique identifier for the agent to revoke.
            reason: The reason for revocation (e.g., 'Compromised', 'Performance').
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO revoked_agents (agent_id, reason, revoked_at) "
                "VALUES (?, ?, ?)",
                (agent_id, reason, datetime.now().isoformat())
            )

    def reinstate_agent(self, agent_id: str) -> None:
        """Removes an agent from the revocation list.

        Args:
            agent_id: The unique identifier for the agent to reinstate.
        """
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM revoked_agents WHERE agent_id = ?", (agent_id,))

    def is_agent_revoked(self, agent_id: str) -> bool:
        """Checks if an agent is currently revoked.

        Args:
            agent_id: The agent's unique identifier.

        Returns:
            True if the agent is in the revoked_agents table, False otherwise.
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT 1 FROM revoked_agents WHERE agent_id = ?", (agent_id,))
            return cursor.fetchone() is not None

    def get_revoked_agents(self) -> List[Dict[str, str]]:
        """Retrieves a list of all currently revoked agents.

        Returns:
            A list of dictionaries containing 'agent_id', 'reason', and 'revoked_at'.
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT agent_id, reason, revoked_at FROM revoked_agents")
            rows = cursor.fetchall()
            return [
                {"agent_id": row[0], "reason": row[1], "revoked_at": row[2]}
                for row in rows
            ]
