# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
SQLite Persistence Backend (Internal)

This module is INTERNAL to KOMPOSOS-IV. Users interact with Category,
never with SQLiteBackend directly. Category owns the backend and calls
it automatically on structural changes.

Same schema as KOMPOSOS-III's KomposOSStore for migration compatibility.
"""

from __future__ import annotations
import sqlite3
import json
from datetime import datetime
from pathlib import Path as FilePath
from typing import Any, Dict, List, Optional, Tuple, Union
from contextlib import contextmanager

import numpy as np

from .types import Object, Morphism, Path


class SQLiteBackend:
    """
    Internal persistence layer for Category.

    Users never instantiate this directly. Category creates and owns it.
    All reads/writes go through Category's public API.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._persistent_conn: Optional[sqlite3.Connection] = None

        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(
                ":memory:",
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            self._persistent_conn.row_factory = sqlite3.Row

        self._init_schema()

    @contextmanager
    def _connection(self):
        """Context manager for database connections."""
        if self._persistent_conn is not None:
            yield self._persistent_conn
            self._persistent_conn.commit()
            return

        conn = sqlite3.connect(
            str(self.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS objects (
                    name TEXT PRIMARY KEY,
                    type_name TEXT NOT NULL DEFAULT 'Object',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    embedding BLOB,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    provenance TEXT NOT NULL DEFAULT 'unknown'
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS morphisms (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    provenance TEXT NOT NULL DEFAULT 'unknown',
                    FOREIGN KEY (source_name) REFERENCES objects(name),
                    FOREIGN KEY (target_name) REFERENCES objects(name)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS paths (
                    id TEXT PRIMARY KEY,
                    morphism_ids TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_name) REFERENCES objects(name),
                    FOREIGN KEY (target_name) REFERENCES objects(name)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS equivalence_classes (
                    name TEXT PRIMARY KEY,
                    member_names TEXT NOT NULL,
                    witness TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS higher_morphisms (
                    name TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    transformation_type TEXT NOT NULL DEFAULT 'homotopy',
                    data TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mor_source ON morphisms(source_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mor_target ON morphisms(target_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mor_name ON morphisms(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_obj_type ON objects(type_name)")

    # =================================================================
    # Object operations
    # =================================================================

    def insert_object(self, obj: Object) -> bool:
        """Insert or update an object. Returns True if inserted."""
        embedding_blob = None
        if obj.embedding is not None:
            embedding_blob = obj.embedding.tobytes()

        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO objects (name, type_name, metadata, embedding, created_at, provenance)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    type_name = excluded.type_name,
                    metadata = excluded.metadata,
                    embedding = excluded.embedding,
                    provenance = excluded.provenance
                """,
                (
                    obj.name,
                    obj.type_name,
                    json.dumps(obj.metadata),
                    embedding_blob,
                    obj.created_at,
                    obj.provenance,
                ),
            )
            return cursor.rowcount == 1

    def get_object(self, name: str) -> Optional[Object]:
        """Get an object by name."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM objects WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_object(row)

    def delete_object(self, name: str) -> bool:
        """Delete an object and its morphisms."""
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM morphisms WHERE source_name = ? OR target_name = ?",
                (name, name),
            )
            cursor = conn.execute("DELETE FROM objects WHERE name = ?", (name,))
            return cursor.rowcount > 0

    def list_objects(self, limit: int = 100) -> List[Object]:
        """List objects with limit."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM objects ORDER BY created_at LIMIT ?", (limit,)
            ).fetchall()
            return [self._row_to_object(row) for row in rows]

    def _row_to_object(self, row: sqlite3.Row) -> Object:
        embedding = None
        if row["embedding"] is not None:
            embedding = np.frombuffer(row["embedding"], dtype=np.float32)
        return Object(
            name=row["name"],
            type_name=row["type_name"],
            metadata=json.loads(row["metadata"]),
            embedding=embedding,
            created_at=row["created_at"],
            provenance=row["provenance"],
        )

    # =================================================================
    # Morphism operations
    # =================================================================

    def insert_morphism(self, mor: Morphism) -> bool:
        """Insert or update a morphism. Returns True if inserted."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO morphisms (id, name, source_name, target_name,
                                       metadata, confidence, created_at, provenance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    metadata = excluded.metadata,
                    confidence = excluded.confidence,
                    provenance = excluded.provenance
                """,
                (
                    mor.id,
                    mor.name,
                    mor.source,
                    mor.target,
                    json.dumps(mor.metadata),
                    mor.confidence,
                    mor.created_at,
                    mor.provenance,
                ),
            )
            return cursor.rowcount == 1

    def get_morphisms_from(self, source: str) -> List[Morphism]:
        """Get all morphisms from a source object."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM morphisms WHERE source_name = ?", (source,)
            ).fetchall()
            return [self._row_to_morphism(row) for row in rows]

    def get_morphisms_to(self, target: str) -> List[Morphism]:
        """Get all morphisms to a target object."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM morphisms WHERE target_name = ?", (target,)
            ).fetchall()
            return [self._row_to_morphism(row) for row in rows]

    def get_morphism(self, mor_id: str) -> Optional[Morphism]:
        """Get a morphism by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM morphisms WHERE id = ?", (mor_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_morphism(row)

    def list_morphisms(self, limit: int = 100) -> List[Morphism]:
        """List morphisms with limit."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM morphisms ORDER BY created_at LIMIT ?", (limit,)
            ).fetchall()
            return [self._row_to_morphism(row) for row in rows]

    def delete_morphism(self, mor_id: str) -> bool:
        """Delete a morphism by ID."""
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM morphisms WHERE id = ?", (mor_id,)
            )
            return cursor.rowcount > 0

    def _row_to_morphism(self, row: sqlite3.Row) -> Morphism:
        return Morphism(
            name=row["name"],
            source=row["source_name"],
            target=row["target_name"],
            metadata=json.loads(row["metadata"]),
            confidence=row["confidence"],
            created_at=row["created_at"],
            provenance=row["provenance"],
        )

    # =================================================================
    # Path finding (BFS)
    # =================================================================

    def find_paths_bfs(
        self, source: str, target: str, max_length: int = 5
    ) -> List[Path]:
        """
        BFS path finding from source to target.

        Returns Path objects with morphism IDs and total weight.
        """
        results: List[Path] = []
        # queue: (current_node, morphism_ids_so_far)
        queue: List[Tuple[str, List[str]]] = [(source, [])]
        visited_paths: set = set()

        while queue:
            current, path_so_far = queue.pop(0)

            if current == target and path_so_far:
                path_key = "->".join(path_so_far)
                if path_key not in visited_paths:
                    visited_paths.add(path_key)
                    results.append(Path(
                        morphism_ids=path_so_far,
                        source=source,
                        target=target,
                    ))
                continue

            if len(path_so_far) >= max_length:
                continue

            morphisms = self.get_morphisms_from(current)
            for mor in morphisms:
                # Avoid revisiting nodes in the current path
                if mor.id not in path_so_far:
                    queue.append((mor.target, path_so_far + [mor.id]))

        return results

    # =================================================================
    # Bulk operations
    # =================================================================

    def bulk_insert_objects(self, objects: List[Object]) -> int:
        """Insert multiple objects in a single transaction."""
        count = 0
        with self._connection() as conn:
            for obj in objects:
                embedding_blob = None
                if obj.embedding is not None:
                    embedding_blob = obj.embedding.tobytes()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO objects
                        (name, type_name, metadata, embedding, created_at, provenance)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        obj.name,
                        obj.type_name,
                        json.dumps(obj.metadata),
                        embedding_blob,
                        obj.created_at,
                        obj.provenance,
                    ),
                )
                count += 1
        return count

    def bulk_insert_morphisms(self, morphisms: List[Morphism]) -> int:
        """Insert multiple morphisms in a single transaction."""
        count = 0
        with self._connection() as conn:
            for mor in morphisms:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO morphisms
                        (id, name, source_name, target_name, metadata,
                         confidence, created_at, provenance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        mor.id,
                        mor.name,
                        mor.source,
                        mor.target,
                        json.dumps(mor.metadata),
                        mor.confidence,
                        mor.created_at,
                        mor.provenance,
                    ),
                )
                count += 1
        return count

    # =================================================================
    # Statistics
    # =================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get store statistics."""
        with self._connection() as conn:
            stats = {
                "objects": conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0],
                "morphisms": conn.execute("SELECT COUNT(*) FROM morphisms").fetchone()[0],
                "paths": conn.execute("SELECT COUNT(*) FROM paths").fetchone()[0],
                "equivalences": conn.execute(
                    "SELECT COUNT(*) FROM equivalence_classes"
                ).fetchone()[0],
                "higher_morphisms": conn.execute(
                    "SELECT COUNT(*) FROM higher_morphisms"
                ).fetchone()[0],
            }

            type_rows = conn.execute(
                "SELECT type_name, COUNT(*) as count FROM objects GROUP BY type_name"
            ).fetchall()
            stats["object_types"] = {
                row["type_name"]: row["count"] for row in type_rows
            }

            mor_rows = conn.execute(
                "SELECT name, COUNT(*) as count FROM morphisms GROUP BY name"
            ).fetchall()
            stats["morphism_types"] = {
                row["name"]: row["count"] for row in mor_rows
            }

            return stats

    # =================================================================
    # Save / export
    # =================================================================

    def save(self, path: str) -> None:
        """Save database to a file (for in-memory stores)."""
        if self._persistent_conn is not None:
            file_conn = sqlite3.connect(path)
            self._persistent_conn.backup(file_conn)
            file_conn.close()
        else:
            with self._connection() as src_conn:
                file_conn = sqlite3.connect(path)
                src_conn.backup(file_conn)
                file_conn.close()

    def close(self) -> None:
        """Close the persistent connection if any."""
        if self._persistent_conn is not None:
            self._persistent_conn.close()
            self._persistent_conn = None
