# Simulation Model - Genealogical Simulation

**Document Version:** 1.0  
**Date:** November 8, 2025  
**Status:** Draft - In Progress

---

## 1. Overview

A **Simulation** represents a complete experimental run with configuration, execution, and results. It orchestrates all entities (Population, Breeders, Generations) and manages the overall simulation lifecycle from initialization through completion to reporting.

---

## 2. Core Responsibilities

1. **Load and validate configuration** (from YAML/JSON)
2. **Initialize simulation state** (database, initial population, pRNG)
3. **Orchestrate generation cycles** (execute generations until completion)
4. **Manage pRNG seeding** (store seed for reproducibility)
5. **Handle persistence** (database connections, batch operations)
6. **Generate reports** (post-simulation analysis and visualization)
7. **Export data** (CSV, JSON formats)

---

## 3. Simulation Lifecycle

### 3.1 Initialization Phase

1. **Load configuration** from YAML/JSON file
2. **Validate configuration** (trait definitions, breeder counts, parameters)
3. **Initialize database** (create schema, tables, indexes)
4. **Initialize pRNG** with seed from configuration (store seed in database)
5. **Create initial population** (founders with genotypes based on initial frequencies)
6. **Initialize breeders** (create breeder instances according to configuration)
7. **Persist initial state** (founders, initial statistics, simulation metadata)

### 3.2 Execution Phase

1. **Loop for N generations** (from configuration)
2. **For each generation:**
   - Create Generation instance with current generation number
   - Execute generation cycle (see [Generation Model](generation.md) section 3.1)
   - Persist generation data
   - Advance generation counter
3. **Track progress** (optional: logging, progress indicators)

### 3.3 Completion Phase

1. **Final persistence** (ensure all data is written)
2. **Calculate final statistics** (overall trends, summary metrics)
3. **Close database connections**
4. **Return simulation results** (metadata, database path, summary)

---

## 4. Configuration

### 4.1 Configuration Structure

```yaml
seed: int                          # pRNG seed for reproducibility
generations: int                   # Number of generations to simulate
initial_population_size: int       # Number of founders
initial_sex_ratio:                 # Sex distribution
  male: float
  female: float
creature_archetype:                # Creature lifecycle parameters
  max_breeding_age:
    male: int
    female: int
  max_litters: int
  lifespan:
    min: int
    max: int
  remove_ineligible_immediately: bool
target_phenotypes: []              # For phenotype-selecting breeders
breeders:                          # Breeder distribution
  random: int
  inbreeding_avoidance: int
  kennel_club: int
  unrestricted_phenotype: int
  kennel_club_config: {}           # Optional kennel club rules
traits: []                         # Trait definitions
```

### 4.2 Configuration Validation

- **Trait definitions:** Valid trait types, genotype frequencies sum to 1.0, valid phenotypes
- **Breeder counts:** Sum equals total number of breeders, non-negative counts
- **Population parameters:** Positive sizes, valid age ranges, valid sex ratios
- **Target phenotypes:** Valid trait IDs, valid phenotype values

---

## 5. Database Management

### 5.1 Database Schema

Simulation creates and manages SQLite database with:

#### 5.1.1 Simulations Table

```sql
CREATE TABLE simulations (
    simulation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seed INTEGER NOT NULL,
    config TEXT NOT NULL,  -- Full YAML/JSON configuration stored as text
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')) DEFAULT 'pending',
    start_time TIMESTAMP NULL,
    end_time TIMESTAMP NULL,
    generations_completed INTEGER CHECK(generations_completed >= 0) DEFAULT 0,
    final_population_size INTEGER CHECK(final_population_size >= 0) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_simulations_status ON simulations(status);
CREATE INDEX idx_simulations_seed ON simulations(seed);
CREATE INDEX idx_simulations_created ON simulations(created_at);
```

**Field Descriptions:**
- `simulation_id`: Unique identifier for each simulation run
- `seed`: pRNG seed used for this simulation (critical for reproducibility)
- `config`: Complete YAML/JSON configuration stored as text (enables exact reproduction)
- `status`: Current state of simulation (pending, running, completed, failed, cancelled)
- `start_time`: When simulation execution began (NULL until started)
- `end_time`: When simulation execution completed (NULL until finished)
- `generations_completed`: Number of generations actually completed (may differ from config if failed early)
- `final_population_size`: Population size at end of simulation (NULL if not completed)
- `created_at`: When simulation record was created
- `updated_at`: Last update timestamp (updated during execution)

**Design Notes:**
- `config` stored as TEXT to preserve exact configuration for reproducibility
- `status` allows tracking simulation lifecycle and handling failures gracefully
- `generations_completed` may be less than configured generations if simulation fails
- Timestamps enable querying simulations by date/time
- Indexes support common queries (by status, seed, creation date)

#### 5.1.2 Other Tables

- Creature tables - See [Creature Model](creature.md) section 7 for schema
- Trait tables - See [Trait Model](trait.md) section 7 for schema
- Generation statistics tables - See [Generation Model](generation.md) section 8 for schema:
  - `generation_stats` - Demographic statistics per generation
  - `generation_genotype_frequencies` - Genotype frequencies (one row per genotype)
  - `generation_trait_stats` - Allele frequencies and heterozygosity (one row per trait)

### 5.2 Seed Storage

- **pRNG seed** stored in `simulations` table
- **Same seed + same config = identical results** (deterministic)
- Seed used to initialize NumPy random generator at start
- Config stored as text enables exact reproduction of simulation conditions

---

## 6. Interface

```python
class Simulation:
    @classmethod
    def from_config(cls, config_path: str, db_path: str | None = None) -> Simulation:
        """
        Create a Simulation instance from a configuration file (convenience factory method).
        
        Args:
            config_path: Path to YAML/JSON configuration file
            db_path: Optional path for SQLite database. If None, database is created
                    in the same directory as config_path with name 
                    'simulation_YYYYMMDD_HHMMSS.db' (e.g., 'simulation_20251108_143022.db')
        
        Returns:
            Initialized Simulation instance
        
        Raises:
            FileNotFoundError: If config_path doesn't exist
            ConfigurationError: If configuration is invalid
        
        Example:
            >>> sim = Simulation.from_config('config.yaml')
            >>> # Database will be: <config_dir>/simulation_20251108_143022.db
        """
        pass
    
    def __init__(self, config_path: str, db_path: str | None = None):
        """
        Initialize simulation from configuration file.
        
        Args:
            config_path: Path to YAML/JSON configuration file
            db_path: Optional path for SQLite database. If None, database is created
                    in the same directory as config_path with name 
                    'simulation_YYYYMMDD_HHMMSS.db' (e.g., 'simulation_20251108_143022.db')
        
        Note:
            Prefer using Simulation.from_config() as it's more convenient.
            This constructor is available for direct instantiation if needed.
        """
        pass
    
    def run(self) -> SimulationResults:
        """
        Execute complete simulation from initialization through all generations.
        
        Returns:
            SimulationResults object with metadata, database path, summary statistics
        
        Raises:
            SimulationError: If simulation fails during execution
        
        Note:
            The database persists after simulation completion and can be queried
            directly using the database_path from SimulationResults.
        """
        pass
    
    def initialize(self) -> None:
        """Initialize simulation state (database, population, breeders)."""
        pass
    
    def execute_generation(self, generation_number: int) -> GenerationStats:
        """Execute single generation cycle."""
        pass
    
    def generate_report(self, output_path: str = None) -> Report:
        """Generate post-simulation report and visualizations."""
        pass
    
    def export_data(self, format: str, output_path: str) -> None:
        """
        Export simulation data.
        
        Args:
            format: 'csv' or 'json'
            output_path: Destination file path
        """
        pass
```

**Database Path Behavior:**
- **Default:** If `db_path` is `None`, the database is created in the same directory as the configuration file
- **Naming:** Auto-generated databases use format `simulation_YYYYMMDD_HHMMSS.db` (e.g., `simulation_20251108_143022.db`)
- **Timestamp:** Generated when simulation is initialized (not when run)
- **Persistence:** Database persists after simulation completion for post-analysis
- **Custom Path:** Users can specify any path for `db_path` to override default behavior

**See:** [API Interface](api-interface.md) for detailed usage examples and patterns.

---

## 7. Implementation Notes

- **Simulation lifecycle:** Update `simulations` table status and timestamps during execution:
  - Set `status='pending'` and `created_at` when simulation record is created
  - Set `status='running'` and `start_time` when execution begins
  - Update `generations_completed` after each generation
  - Set `status='completed'`, `end_time`, and `final_population_size` on successful completion
  - Set `status='failed'` and `end_time` on error
  - Update `updated_at` whenever status or progress changes
- **Deterministic execution:** Same seed + config produces identical results
- **Database efficiency:** Use batch inserts, transactions, prepared statements (see [Creature Model](creature.md) section 8.1)
- **Memory management:** Don't load all generations into memory; query database as needed
- **Error handling:** Validate configuration early, handle database errors gracefully, update status to 'failed' on error
- **Progress tracking:** Optional logging/progress indicators for long simulations
- **Resource cleanup:** Ensure database connections are closed properly
- **Breeder distribution:** Create breeder instances according to configuration counts
- **Config storage:** Store full YAML/JSON config as TEXT in database for exact reproduction

---

## 8. Simulation Results

After completion, simulation returns:

```python
@dataclass
class SimulationResults:
    simulation_id: int              # Database ID (from simulations table)
    seed: int                      # pRNG seed used
    status: str                    # 'completed', 'failed', or 'cancelled'
    generations_completed: int     # Actual generations run
    final_population_size: int     # Population at end (None if not completed)
    database_path: str             # Path to SQLite database
    config: dict                   # Configuration used (parsed from stored config text)
    start_time: datetime           # Simulation start timestamp
    end_time: datetime             # Simulation end timestamp
    duration_seconds: float        # Execution time (end_time - start_time)
```

**Note:** 
- The `SimulationResults` object is derived from the `simulations` table record. The `config` field is parsed from the stored TEXT field for convenience.
- The `database_path` is always provided and points to a persistent SQLite database that can be queried after simulation completion.
- Database persists on disk - it does not disappear when the program ends.

---

## 9. Reporting & Export

### 9.1 Report Generation

- **Trait prevalence graphs** (line charts over generations)
- **Population statistics** (size, demographics over time)
- **Genetic diversity metrics** (heterozygosity, allele frequencies)
- **Summary statistics** (final state, trends)

### 9.2 Data Export

- **CSV export:** Creature data, genotype frequencies, generation statistics
- **JSON export:** Complete simulation data in structured format
- **SQLite access:** Direct database queries for custom analysis

---

## 10. Relationship to Other Entities

- **Configuration:** Defines simulation parameters
- **Population:** Manages working pool of creatures (see [Population Model](population.md))
- **Breeder:** Strategy instances for mate selection (see [Breeder Model](breeder.md))
- **Generation:** Individual generation cycles (see [Generation Model](generation.md))
- **Creature:** Individual organisms in simulation (see [Creature Model](creature.md))
- **Trait:** Genetic characteristics being tracked (see [Trait Model](trait.md))

---

## 11. Error Handling

- **Configuration errors:** Validate early, provide clear error messages
- **Database errors:** Handle connection issues, transaction failures
- **Runtime errors:** Log errors, attempt graceful degradation
- **Resource errors:** Handle memory constraints, disk space issues

---

## 12. Performance Considerations

- **Batch operations:** Group database writes for efficiency
- **Lazy evaluation:** Calculate statistics only when needed
- **Index optimization:** Create indexes for common query patterns
- **Memory efficiency:** Stream large datasets, don't load everything

---

**Status:** Draft - Ready for review. Next: Begin implementation phase.

