"""Database schema creation for gene_sim."""

import sqlite3
from typing import Optional

from ..exceptions import DatabaseError


def create_schema(conn: sqlite3.Connection) -> None:
    """
    Create all database tables, indexes, and constraints.
    
    Args:
        conn: SQLite database connection
        
    Raises:
        DatabaseError: If schema creation fails
    """
    try:
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create tables in order (respecting foreign key dependencies)
        
        # 1. Simulations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulations (
                simulation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                seed INTEGER NOT NULL,
                config TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')) DEFAULT 'pending',
                start_time TIMESTAMP NULL,
                end_time TIMESTAMP NULL,
                generations_completed INTEGER CHECK(generations_completed >= 0) DEFAULT 0,
                final_population_size INTEGER CHECK(final_population_size >= 0) NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Traits table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS traits (
                trait_id INTEGER PRIMARY KEY CHECK(trait_id >= 0 AND trait_id < 100),
                name TEXT NOT NULL,
                trait_type TEXT NOT NULL CHECK(trait_type IN (
                    'SIMPLE_MENDELIAN', 
                    'INCOMPLETE_DOMINANCE', 
                    'CODOMINANCE', 
                    'SEX_LINKED', 
                    'POLYGENIC'
                ))
            )
        """)
        
        # 3. Genotypes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS genotypes (
                genotype_id INTEGER PRIMARY KEY AUTOINCREMENT,
                trait_id INTEGER NOT NULL,
                genotype TEXT NOT NULL,
                phenotype TEXT NOT NULL,
                sex TEXT,
                initial_freq REAL NOT NULL CHECK(initial_freq >= 0.0 AND initial_freq <= 1.0),
                FOREIGN KEY (trait_id) REFERENCES traits(trait_id) ON DELETE CASCADE,
                UNIQUE(trait_id, genotype, sex)
            )
        """)
        
        # 3.5 Breeders table (to track breeder IDs and types)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS breeders (
                breeder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                simulation_id INTEGER NOT NULL,
                breeder_index INTEGER NOT NULL CHECK(breeder_index >= 0),
                breeder_type TEXT NOT NULL CHECK(breeder_type IN ('random', 'inbreeding_avoidance', 'kennel_club', 'mill')),
                FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
                UNIQUE(simulation_id, breeder_index)
            )
        """)
        
        # 4. Creatures table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS creatures (
                creature_id INTEGER PRIMARY KEY AUTOINCREMENT,
                simulation_id INTEGER NOT NULL,
                birth_cycle INTEGER NOT NULL CHECK(birth_cycle >= 0),
                sex TEXT CHECK(sex IN ('male', 'female')) NULL,
                parent1_id INTEGER NULL,
                parent2_id INTEGER NULL,
                breeder_id INTEGER NULL,
                produced_by_breeder_id INTEGER NULL,
                inbreeding_coefficient REAL NOT NULL CHECK(inbreeding_coefficient >= 0.0 AND inbreeding_coefficient <= 1.0) DEFAULT 0.0,
                lifespan INTEGER NOT NULL CHECK(lifespan > 0),
                is_alive BOOLEAN DEFAULT 1,
                conception_cycle INTEGER NULL,
                sexual_maturity_cycle INTEGER NULL,
                max_fertility_age_cycle INTEGER NULL,
                gestation_end_cycle INTEGER NULL,
                nursing_end_cycle INTEGER NULL,
                generation INTEGER NULL,
                FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
                FOREIGN KEY (parent1_id) REFERENCES creatures(creature_id) ON DELETE SET NULL,
                FOREIGN KEY (parent2_id) REFERENCES creatures(creature_id) ON DELETE SET NULL,
                FOREIGN KEY (breeder_id) REFERENCES breeders(breeder_id) ON DELETE SET NULL,
                FOREIGN KEY (produced_by_breeder_id) REFERENCES breeders(breeder_id) ON DELETE SET NULL,
                CHECK((birth_cycle = 0) = (parent1_id IS NULL)),
                CHECK((birth_cycle = 0) = (parent2_id IS NULL))
            )
        """)
        
        # 4.1 Creature ownership history table (to track ownership changes)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS creature_ownership_history (
                ownership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creature_id INTEGER NOT NULL,
                breeder_id INTEGER NOT NULL,
                transfer_generation INTEGER NOT NULL CHECK(transfer_generation >= 0),
                FOREIGN KEY (creature_id) REFERENCES creatures(creature_id) ON DELETE CASCADE,
                FOREIGN KEY (breeder_id) REFERENCES breeders(breeder_id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creature_ownership_creature ON creature_ownership_history(creature_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creature_ownership_breeder ON creature_ownership_history(breeder_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creature_ownership_generation ON creature_ownership_history(transfer_generation)")
        
        # 5. Creature genotypes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS creature_genotypes (
                creature_id INTEGER NOT NULL,
                trait_id INTEGER NOT NULL CHECK(trait_id >= 0),
                genotype TEXT NOT NULL,
                FOREIGN KEY (creature_id) REFERENCES creatures(creature_id) ON DELETE CASCADE,
                FOREIGN KEY (trait_id) REFERENCES traits(trait_id) ON DELETE CASCADE,
                PRIMARY KEY (creature_id, trait_id)
            )
        """)
        
        # 6. Generation stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generation_stats (
                simulation_id INTEGER NOT NULL,
                generation INTEGER NOT NULL CHECK(generation >= 0),
                population_size INTEGER NOT NULL CHECK(population_size >= 0),
                eligible_males INTEGER NOT NULL CHECK(eligible_males >= 0),
                eligible_females INTEGER NOT NULL CHECK(eligible_females >= 0),
                births INTEGER NOT NULL CHECK(births >= 0),
                deaths INTEGER NOT NULL CHECK(deaths >= 0),
                FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
                PRIMARY KEY (simulation_id, generation)
            )
        """)
        
        # 7. Generation genotype frequencies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generation_genotype_frequencies (
                simulation_id INTEGER NOT NULL,
                generation INTEGER NOT NULL CHECK(generation >= 0),
                trait_id INTEGER NOT NULL CHECK(trait_id >= 0),
                genotype TEXT NOT NULL,
                frequency REAL NOT NULL CHECK(frequency >= 0 AND frequency <= 1),
                FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
                FOREIGN KEY (simulation_id, generation) REFERENCES generation_stats(simulation_id, generation) ON DELETE CASCADE,
                FOREIGN KEY (trait_id) REFERENCES traits(trait_id) ON DELETE CASCADE,
                PRIMARY KEY (simulation_id, generation, trait_id, genotype)
            )
        """)
        
        # 8. Generation trait stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generation_trait_stats (
                simulation_id INTEGER NOT NULL,
                generation INTEGER NOT NULL CHECK(generation >= 0),
                trait_id INTEGER NOT NULL CHECK(trait_id >= 0),
                allele_frequencies JSON NOT NULL,
                heterozygosity REAL NOT NULL CHECK(heterozygosity >= 0 AND heterozygosity <= 1),
                genotype_diversity INTEGER NOT NULL CHECK(genotype_diversity >= 0),
                FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
                FOREIGN KEY (simulation_id, generation) REFERENCES generation_stats(simulation_id, generation) ON DELETE CASCADE,
                FOREIGN KEY (trait_id) REFERENCES traits(trait_id) ON DELETE CASCADE,
                PRIMARY KEY (simulation_id, generation, trait_id)
            )
        """)
        
        # Create indexes
        
        # Simulations indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_simulations_status ON simulations(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_simulations_seed ON simulations(seed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_simulations_created ON simulations(created_at)")
        
        # Traits indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_traits_type ON traits(trait_type)")
        
        # Genotypes indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_genotypes_trait ON genotypes(trait_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_genotypes_phenotype ON genotypes(trait_id, phenotype)")
        
        # Creatures indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creatures_birth_cycle ON creatures(simulation_id, birth_cycle)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creatures_parents ON creatures(parent1_id, parent2_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creatures_breeding_eligibility ON creatures(simulation_id, sex, birth_cycle, is_alive)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creatures_inbreeding ON creatures(simulation_id, inbreeding_coefficient)")
        
        # Creature genotypes indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creature_genotypes_trait ON creature_genotypes(trait_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creature_genotypes_genotype ON creature_genotypes(genotype)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creature_genotypes_creature ON creature_genotypes(creature_id)")
        
        # Generation stats indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_generation_stats_generation ON generation_stats(simulation_id, generation)")
        
        # Generation genotype frequencies indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_genotype_freq_generation ON generation_genotype_frequencies(simulation_id, generation)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_genotype_freq_trait ON generation_genotype_frequencies(trait_id)")
        
        # Generation trait stats indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trait_stats_generation ON generation_trait_stats(simulation_id, generation)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trait_stats_trait ON generation_trait_stats(trait_id)")
        
        conn.commit()
        
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f"Failed to create database schema: {e}") from e


def drop_schema(conn: sqlite3.Connection) -> None:
    """
    Drop all database tables (for testing/cleanup).
    
    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()
    
    # Drop tables in reverse order (respecting foreign key dependencies)
    tables = [
        'generation_trait_stats',
        'generation_genotype_frequencies',
        'generation_stats',
        'creature_genotypes',
        'creatures',
        'genotypes',
        'traits',
        'simulations',
    ]
    
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    
    conn.commit()

