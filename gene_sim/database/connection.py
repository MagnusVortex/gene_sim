"""Database connection management for gene_sim."""

import sqlite3
import os
from pathlib import Path
from typing import Optional

from ..exceptions import DatabaseError


def get_db_connection(db_path: str) -> sqlite3.Connection:
    """
    Get a database connection with foreign keys enabled.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        SQLite connection with foreign keys enabled
        
    Raises:
        DatabaseError: If connection fails
    """
    try:
        # Ensure directory exists
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to connect to database at {db_path}: {e}") from e


def create_database(db_path: str) -> sqlite3.Connection:
    """
    Create a new database with schema.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        SQLite connection to the new database
        
    Raises:
        DatabaseError: If database creation fails
    """
    from .schema import create_schema
    
    conn = get_db_connection(db_path)
    create_schema(conn)
    return conn

