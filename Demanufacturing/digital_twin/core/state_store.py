"""
core/state_store.py

SQLite-based persistence for holon states.

ARCHITECTURAL CONSTRAINT:
This module MUST NEVER import from mock_hardware/.
"""

import sqlite3
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import threading


class StateStore:
    """
    SQLite-based state persistence for the digital twin.
    
    Stores holon states with full history for replay and analysis.
    Thread-safe for concurrent access from MQTT callbacks.
    """
    
    def __init__(self, db_path: str = ":memory:"):
        """
        Initialize the state store.
        
        Args:
            db_path: Path to SQLite database, or ":memory:" for in-memory storage
        """
        self.db_path = db_path
        self._local = threading.local()
        self._init_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            # Initialize schema for this thread's connection
            self._init_schema_for_connection(self._local.conn)
        return self._local.conn
    
    def _init_schema(self):
        """Initialize database schema."""
        conn = self._get_connection()
        self._init_schema_for_connection(conn)
    
    def _init_schema_for_connection(self, conn: sqlite3.Connection):
        """Initialize database schema for a specific connection."""
        cursor = conn.cursor()
        
        # Current holon states
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS holons (
                holon_id TEXT PRIMARY KEY,
                holon_type TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # State history for analysis
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                holon_id TEXT NOT NULL,
                patches_json TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (holon_id) REFERENCES holons(holon_id)
            )
        """)
        
        # Indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_holon 
            ON state_history(holon_id, timestamp)
        """)
        
        conn.commit()
    
    def upsert_holon(self, holon_id: str, holon_type: str, state: Dict[str, Any]):
        """
        Insert or update a holon's current state.
        
        Args:
            holon_id: Unique holon identifier
            holon_type: Type of holon (product, robot, operator)
            state: Full state dictionary
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        state_json = json.dumps(state)
        
        cursor.execute("""
            INSERT INTO holons (holon_id, holon_type, state_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(holon_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
        """, (holon_id, holon_type, state_json, now, now))
        
        conn.commit()
    
    def record_patches(self, holon_id: str, patches: Dict[str, Any]):
        """
        Record a patch event to state history.
        
        Args:
            holon_id: Holon that was patched
            patches: The patches that were applied
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO state_history (holon_id, patches_json, timestamp)
            VALUES (?, ?, ?)
        """, (holon_id, json.dumps(patches), datetime.now().isoformat()))
        
        conn.commit()
    
    def get_holon(self, holon_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve current state of a holon.
        
        Args:
            holon_id: Holon identifier
            
        Returns:
            State dictionary or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT state_json FROM holons WHERE holon_id = ?",
            (holon_id,)
        )
        row = cursor.fetchone()
        
        if row:
            return json.loads(row["state_json"])
        return None
    
    def get_all_holons(self, holon_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all holons, optionally filtered by type.
        
        Args:
            holon_type: Optional filter by holon type
            
        Returns:
            List of state dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if holon_type:
            cursor.execute(
                "SELECT state_json FROM holons WHERE holon_type = ?",
                (holon_type,)
            )
        else:
            cursor.execute("SELECT state_json FROM holons")
        
        return [json.loads(row["state_json"]) for row in cursor.fetchall()]
    
    def get_history(
        self, 
        holon_id: str, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve patch history for a holon.
        
        Args:
            holon_id: Holon identifier
            limit: Maximum number of records
            
        Returns:
            List of patch records with timestamps
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT patches_json, timestamp 
            FROM state_history 
            WHERE holon_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (holon_id, limit))
        
        return [
            {"patches": json.loads(row["patches_json"]), "timestamp": row["timestamp"]}
            for row in cursor.fetchall()
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get summary statistics about stored holons."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT holon_type, COUNT(*) as count
            FROM holons
            GROUP BY holon_type
        """)
        
        type_counts = {row["holon_type"]: row["count"] for row in cursor.fetchall()}
        
        cursor.execute("SELECT COUNT(*) as count FROM state_history")
        history_count = cursor.fetchone()["count"]
        
        return {
            "holon_counts": type_counts,
            "total_holons": sum(type_counts.values()),
            "history_records": history_count,
        }
    
    def clear(self):
        """Clear all stored data."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM state_history")
        cursor.execute("DELETE FROM holons")
        conn.commit()
