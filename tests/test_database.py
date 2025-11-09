"""Tests for database layer."""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from gene_sim.database import create_database, get_db_connection
from gene_sim.database.schema import create_schema, drop_schema


def test_create_database():
    """Test database creation."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        conn = create_database(db_path)
        assert conn is not None
        
        # Check that tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = [
            'simulations', 'traits', 'genotypes', 'creatures',
            'creature_genotypes', 'generation_stats',
            'generation_genotype_frequencies', 'generation_trait_stats'
        ]
        
        for table in expected_tables:
            assert table in tables
        
        conn.close()
    finally:
        Path(db_path).unlink()


def test_schema_foreign_keys():
    """Test that foreign keys are enforced."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        conn = create_database(db_path)
        cursor = conn.cursor()
        
        # Try to insert creature with invalid simulation_id
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO creatures (
                    simulation_id, birth_cycle, lifespan
                ) VALUES (999, 0, 10)
            """)
            conn.commit()
        
        conn.close()
    finally:
        try:
            Path(db_path).unlink()
        except PermissionError:
            pass  # File may be locked on Windows


def test_get_db_connection():
    """Test getting database connection."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        conn = get_db_connection(db_path)
        assert conn is not None
        
        # Check foreign keys are enabled
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys")
        result = cursor.fetchone()
        assert result[0] == 1  # Foreign keys enabled
        
        conn.close()
    finally:
        Path(db_path).unlink()

