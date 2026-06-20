# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
SQLite Persistence Backend (Internal)

This module is INTERNAL to OPERADUM. Users interact with Operad, never with
SQLiteBackend directly. Operad owns the backend and calls it automatically
on structural changes -- the dual of KOMPOSOS-IV's core/persistence.py.

Stores three tables:
  colours      -- interface types
  operations   -- build rules (with their resource cost)
  composites   -- saved wirings (serialized as a wiring DSL string)

Deleting a colour cascades to operations that mention it.
"""

from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from typing import List, Optional

from .types import Colour, Operation


class SQLiteBackend:
    """
    Internal persistence layer for Operad.

    Users never instantiate this directly. Operad creates and owns it.
    All reads/writes go through Operad's public API.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._persistent_conn: Optional[sqlite3.Connection] = None

        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:")
            self._persistent_conn.row_factory = sqlite3.Row

        self._init_schema()

    @contextmanager
    def _connection(self):
        """Context manager for database connections."""
        if self._persistent_conn is not None:
            yield self._persistent_conn
            self._persistent_conn.commit()
            return

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS colours (
                    name TEXT PRIMARY KEY,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    provenance TEXT NOT NULL DEFAULT 'unknown'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    inputs TEXT NOT NULL DEFAULT '[]',
                    output TEXT NOT NULL,
                    cost TEXT NOT NULL DEFAULT '{}',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    provenance TEXT NOT NULL DEFAULT 'unknown'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS composites (
                    id TEXT PRIMARY KEY,
                    wiring TEXT NOT NULL,
                    output TEXT NOT NULL,
                    inputs TEXT NOT NULL DEFAULT '[]',
                    cost TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

    # ---------------- Colours ----------------

    def insert_colour(self, colour: Colour) -> None:
        with self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO colours (name, metadata, provenance) "
                "VALUES (?, ?, ?)",
                (colour.name, json.dumps(colour.metadata), colour.provenance),
            )

    def get_colour(self, name: str) -> Optional[Colour]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM colours WHERE name = ?", (name,)
            ).fetchone()
        if row is None:
            return None
        return Colour(
            name=row["name"],
            metadata=json.loads(row["metadata"]),
            provenance=row["provenance"],
        )

    def list_colours(self) -> List[Colour]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM colours").fetchall()
        return [
            Colour(name=r["name"], metadata=json.loads(r["metadata"]),
                   provenance=r["provenance"])
            for r in rows
        ]

    def delete_colour(self, name: str) -> None:
        """Delete a colour and cascade to every operation that mentions it."""
        with self._connection() as conn:
            conn.execute("DELETE FROM colours WHERE name = ?", (name,))
            # Cascade: drop operations whose output or any input is this colour.
            rows = conn.execute("SELECT id, inputs, output FROM operations").fetchall()
            doomed = [
                r["id"] for r in rows
                if r["output"] == name or name in json.loads(r["inputs"])
            ]
            for oid in doomed:
                conn.execute("DELETE FROM operations WHERE id = ?", (oid,))

    # ---------------- Operations ----------------

    def insert_operation(self, op: Operation) -> None:
        with self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO operations "
                "(id, name, inputs, output, cost, metadata, provenance) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    op.id, op.name, json.dumps(op.inputs), op.output,
                    json.dumps(op.cost), json.dumps(op.metadata), op.provenance,
                ),
            )

    def get_operation(self, op_id: str) -> Optional[Operation]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM operations WHERE id = ?", (op_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_op(row)

    def list_operations(self) -> List[Operation]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM operations").fetchall()
        return [self._row_to_op(r) for r in rows]

    def delete_operation(self, op_id: str) -> None:
        with self._connection() as conn:
            conn.execute("DELETE FROM operations WHERE id = ?", (op_id,))

    @staticmethod
    def _row_to_op(row: sqlite3.Row) -> Operation:
        return Operation(
            name=row["name"],
            inputs=json.loads(row["inputs"]),
            output=row["output"],
            cost=json.loads(row["cost"]),
            metadata=json.loads(row["metadata"]),
            provenance=row["provenance"],
        )

    # ---------------- Composites ----------------

    def insert_composite(self, comp_id: str, wiring: str, output: str,
                         inputs: List[str], cost: dict) -> None:
        with self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO composites "
                "(id, wiring, output, inputs, cost) VALUES (?, ?, ?, ?, ?)",
                (comp_id, wiring, output, json.dumps(inputs), json.dumps(cost)),
            )
