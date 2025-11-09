"""Simulation engine for gene_sim."""

import json
import sqlite3
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import numpy as np

from .config import load_config, SimulationConfig
from .exceptions import SimulationError, DatabaseError
from .database import create_database, get_db_connection
from .models.trait import Trait
from .models.population import Population
from .models.generation import Generation
from .models.breeder import (
    RandomBreeder, InbreedingAvoidanceBreeder,
    KennelClubBreeder, UnrestrictedPhenotypeBreeder
)
from .models.creature import Creature


@dataclass
class SimulationResults:
    """Results from a completed simulation."""
    simulation_id: int
    seed: int
    status: str
    generations_completed: int
    final_population_size: Optional[int]
    database_path: str
    config: dict
    start_time: datetime
    end_time: datetime
    duration_seconds: float


class Simulation:
    """Main simulation class that orchestrates the simulation lifecycle."""
    
    def __init__(self, config_path: str, db_path: Optional[str] = None):
        """
        Initialize simulation from configuration file.
        
        Args:
            config_path: Path to YAML/JSON configuration file
            db_path: Optional path for SQLite database. If None, database is created
                    in the same directory as config_path with name 
                    'simulation_YYYYMMDD_HHMMSS.db'
        """
        self.config_path = config_path
        self.config = load_config(config_path)
        self.db_path = db_path or self._generate_db_path()
        self.db_conn: Optional[sqlite3.Connection] = None
        self.simulation_id: Optional[int] = None
        self.rng: Optional[np.random.Generator] = None
        self.population: Optional[Population] = None
        self.breeders: list = []
        self.traits: list = []
    
    @classmethod
    def from_config(cls, config_path: str, db_path: Optional[str] = None) -> 'Simulation':
        """
        Create a Simulation instance from a configuration file (convenience factory method).
        
        Args:
            config_path: Path to YAML/JSON configuration file
            db_path: Optional path for SQLite database. If None, database is created
                    in the same directory as config_path with name 
                    'simulation_YYYYMMDD_HHMMSS.db'
        
        Returns:
            Initialized Simulation instance
        """
        return cls(config_path, db_path)
    
    def _generate_db_path(self) -> str:
        """Generate default database path based on config file location."""
        config_dir = Path(self.config_path).parent
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_name = f"simulation_{timestamp}.db"
        return str(config_dir / db_name)
    
    def initialize(self) -> None:
        """Initialize simulation state (database, population, breeders)."""
        try:
            # Create database and schema
            self.db_conn = create_database(self.db_path)
            
            # Initialize RNG with seed
            self.rng = np.random.Generator(np.random.PCG64(self.config.seed))
            
            # Load traits
            self.traits = [
                Trait.from_config({
                    'trait_id': tc.trait_id,
                    'name': tc.name,
                    'trait_type': tc.trait_type,  # Already a string from config
                    'genotypes': tc.genotypes  # Already a list of dicts
                })
                for tc in self.config.traits
            ]
            
            # Persist traits to database
            self._persist_traits()
            
            # Create breeders
            self._create_breeders()
            
            # Create initial population
            self.population = Population()
            self._create_initial_population()
            
            # Create simulation record (must be done before persisting founders)
            self._create_simulation_record()
            
            # Persist founders immediately so they all have IDs from the start
            self._persist_founders()
            
        except Exception as e:
            raise SimulationError(f"Failed to initialize simulation: {e}") from e
    
    def _persist_traits(self) -> None:
        """Persist trait definitions to database."""
        cursor = self.db_conn.cursor()
        
        for trait in self.traits:
            # Insert trait (ignore if already exists - allows multiple simulations in same DB)
            cursor.execute("""
                INSERT OR IGNORE INTO traits (trait_id, name, trait_type)
                VALUES (?, ?, ?)
            """, (trait.trait_id, trait.name, trait.trait_type.value))
            
            # Insert genotypes (ignore if already exists)
            for genotype in trait.genotypes:
                cursor.execute("""
                    INSERT OR IGNORE INTO genotypes (
                        trait_id, genotype, phenotype, sex, initial_freq
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    trait.trait_id,
                    genotype.genotype,
                    genotype.phenotype,
                    genotype.sex,
                    genotype.initial_freq
                ))
        
        self.db_conn.commit()
    
    def _create_breeders(self) -> None:
        """Create breeder instances according to configuration."""
        breeders = []
        
        # Random breeders
        for _ in range(self.config.breeders.random):
            breeders.append(RandomBreeder())
        
        # Inbreeding avoidance breeders
        for _ in range(self.config.breeders.inbreeding_avoidance):
            breeders.append(InbreedingAvoidanceBreeder(max_inbreeding_coefficient=0.25))
        
        # Kennel club breeders
        kennel_config = self.config.breeders.kennel_club_config or {}
        for _ in range(self.config.breeders.kennel_club):
            breeders.append(KennelClubBreeder(
                target_phenotypes=self.config.target_phenotypes,
                max_inbreeding_coefficient=kennel_config.get('max_inbreeding_coefficient'),
                required_phenotype_ranges=kennel_config.get('required_phenotype_ranges', [])
            ))
        
        # Unrestricted phenotype breeders
        for _ in range(self.config.breeders.unrestricted_phenotype):
            breeders.append(UnrestrictedPhenotypeBreeder(
                target_phenotypes=self.config.target_phenotypes
            ))
        
        self.breeders = breeders
    
    def _create_initial_population(self) -> None:
        """Create initial population of founders."""
        founders = []
        
        # Determine max trait_id for genome size
        max_trait_id = max(t.trait_id for t in self.traits) if self.traits else 0
        
        for i in range(self.config.initial_population_size):
            # Determine sex based on initial_sex_ratio
            sex_prob = self.config.initial_sex_ratio['female']
            sex = 'female' if self.rng.random() < sex_prob else 'male'
            
            # Create genome by sampling genotypes
            genome: list = [None] * (max_trait_id + 1)
            for trait in self.traits:
                genotype = trait.get_genotype_by_frequency(self.rng)
                genome[trait.trait_id] = genotype.genotype
            
            # Sample lifespan
            lifespan = self.rng.integers(
                self.config.creature_archetype.lifespan_min,
                self.config.creature_archetype.lifespan_max + 1
            )
            
            # Initialize litters_remaining for females
            litters_remaining = (
                self.config.creature_archetype.max_litters
                if sex == 'female' else 0
            )
            
            creature = Creature(
                simulation_id=0,  # Will be updated after simulation record created
                birth_generation=0,
                sex=sex,
                genome=genome,
                parent1_id=None,
                parent2_id=None,
                inbreeding_coefficient=0.0,
                litters_remaining=litters_remaining,
                lifespan=lifespan,
                is_alive=True
            )
            
            founders.append(creature)
        
        # Add founders to population with current_generation=0
        self.population.add_creatures(founders, current_generation=0)
    
    def _create_simulation_record(self) -> None:
        """Create simulation record in database."""
        cursor = self.db_conn.cursor()
        
        # Store config as JSON text
        config_text = json.dumps(self.config.raw_config)
        
        cursor.execute("""
            INSERT INTO simulations (
                seed, config, status, start_time
            ) VALUES (?, ?, 'running', ?)
        """, (self.config.seed, config_text, datetime.now().isoformat()))
        
        self.simulation_id = cursor.lastrowid
        
        # Update creature simulation_ids (will be persisted in _persist_founders)
        for creature in self.population.creatures:
            creature.simulation_id = self.simulation_id
    
    def _persist_founders(self) -> None:
        """
        Persist founder creatures to database immediately upon creation.
        
        All creatures must be persisted immediately to ensure they have IDs from the start.
        This method persists all founders right after they are created and before any
        breeding occurs.
        """
        # Get all founders (birth_generation = 0)
        founders = [c for c in self.population.creatures if c.birth_generation == 0]
        
        if founders:
            # Persist founders to database immediately
            self.population._persist_creatures(self.db_conn, self.simulation_id, founders)
        
        self.db_conn.commit()
    
    def run(self) -> SimulationResults:
        """
        Execute complete simulation from initialization through all generations.
        
        Returns:
            SimulationResults object with metadata, database path, summary
        
        Raises:
            SimulationError: If simulation fails during execution
        """
        start_time = datetime.now()
        
        try:
            # Initialize if not already done
            if self.db_conn is None:
                self.initialize()
            
            # Execute generations
            generation = Generation(0)
            
            for gen_num in range(self.config.generations):
                generation.generation_number = gen_num
                
                stats = generation.execute_cycle(
                    population=self.population,
                    breeders=self.breeders,
                    traits=self.traits,
                    rng=self.rng,
                    db_conn=self.db_conn,
                    simulation_id=self.simulation_id,
                    config=self.config
                )
                
                # Update simulation progress
                self._update_simulation_progress(gen_num + 1, len(self.population.creatures))
            
            # Finalize simulation
            end_time = datetime.now()
            self._finalize_simulation(end_time, len(self.population.creatures))
            
            # Build results
            duration = (end_time - start_time).total_seconds()
            
            return SimulationResults(
                simulation_id=self.simulation_id,
                seed=self.config.seed,
                status='completed',
                generations_completed=self.config.generations,
                final_population_size=len(self.population.creatures),
                database_path=self.db_path,
                config=self.config.raw_config,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration
            )
            
        except Exception as e:
            # Mark simulation as failed
            if self.db_conn and self.simulation_id:
                try:
                    cursor = self.db_conn.cursor()
                    cursor.execute("""
                        UPDATE simulations
                        SET status = 'failed', end_time = ?
                        WHERE simulation_id = ?
                    """, (datetime.now().isoformat(), self.simulation_id))
                    self.db_conn.commit()
                except:
                    pass
            
            raise SimulationError(f"Simulation failed: {e}") from e
        finally:
            # Close database connection
            if self.db_conn:
                self.db_conn.close()
    
    def _update_simulation_progress(self, generations_completed: int, population_size: int) -> None:
        """Update simulation progress in database."""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            UPDATE simulations
            SET generations_completed = ?, updated_at = ?
            WHERE simulation_id = ?
        """, (generations_completed, datetime.now().isoformat(), self.simulation_id))
        self.db_conn.commit()
    
    def _finalize_simulation(self, end_time: datetime, final_population_size: int) -> None:
        """Finalize simulation record."""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            UPDATE simulations
            SET status = 'completed', end_time = ?, final_population_size = ?, updated_at = ?
            WHERE simulation_id = ?
        """, (end_time.isoformat(), final_population_size, end_time.isoformat(), self.simulation_id))
        self.db_conn.commit()

