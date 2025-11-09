# Generation Model - Genealogical Simulation

**Document Version:** 1.0  
**Date:** November 8, 2025  
**Status:** Draft - In Progress

---

## 1. Overview

A **Generation** represents a single iteration in the simulation timeline. It tracks the state of the population at a specific point in time and manages the transition from one generation to the next. The generation number is maintained in memory during simulation execution; only creature `birth_generation` values are persisted to the database.

---

## 2. Core Responsibilities

1. **Track generation number** (in-memory counter during simulation)
2. **Coordinate generation cycle** (breeding, reproduction, removal of aged-out creatures)
3. **Calculate generation statistics** before persistence
4. **Persist generation data** to database (creatures, genotypes, statistics)
5. **Advance to next generation** (increment counter)

---

## 3. Generation Lifecycle

### 3.1 Generation Cycle Steps

1. **Filter eligible creatures** (see [Creature Model](creature.md) section 6 for eligibility criteria)
2. **Select mating pairs** (via configured breeders - see [Breeder Model](breeder.md))
3. **Reproduce** (gamete formation, offspring creation - see [Creature Model](creature.md) section 5)
4. **Add offspring** to population (see [Population Model](population.md))
5. **Get aged-out creatures** for current generation (see [Population Model](population.md))
6. **Remove aged-out creatures** (see [Creature Model](creature.md) section 8.3 for persistence)
7. **Calculate statistics** (genotype frequencies, diversity metrics)
8. **Persist generation statistics** to database
9. **Advance generation** (increment generation counter)

### 3.2 Generation Numbering

- **Generation 0:** Initial population (founders)
- **Generation 1:** First offspring generation
- **Generation N:** Nth generation of offspring

**Note:** Generation number is stored in memory during simulation. Only creature `birth_generation` values are persisted to the database. Generation statistics are stored with a `generation` field in database tables.

---

## 4. Statistics Calculation

Generation statistics are calculated before persistence:

**Demographic:**
- Total population size
- Number of eligible males/females
- Age distribution
- Sex ratio
- Number of births (offspring created this generation)
- Number of deaths (creatures aged out this generation)

**Genetic:**
- Genotype frequencies per trait (from working pool)
- Allele frequencies per trait
- Heterozygosity per trait
- Genotype diversity per trait (number of distinct genotypes present)
- Phenotype distributions (can be calculated post-simulation from persisted data)

**Note:** Statistics are calculated from the in-memory working pool before creatures are persisted. This ensures accurate counts before any removals occur.

---

## 5. Database Persistence

Generation coordinates persistence of:
- **Generation Statistics:** Aggregated metrics for this generation (see section 4):
  - Demographic stats → `generation_stats` table
  - Genotype frequencies → `generation_genotype_frequencies` table (one row per genotype)
  - Allele frequencies and heterozygosity → `generation_trait_stats` table (one row per trait)
- **Creatures:** Aged-out creatures are persisted by Population before removal (see [Creature Model](creature.md) section 8.3 for persistence details)

---

## 6. Interface

```python
class Generation:
    def __init__(self, generation_number: int, config: SimulationConfig):
        """Initialize generation with number and configuration."""
        pass
    
    def execute_cycle(
        self, 
        population: Population, 
        breeders: List[Breeder],
        rng: np.random.Generator,
        db_connection: sqlite3.Connection
    ) -> GenerationStats:
        """
        Execute one complete generation cycle.
        
        Args:
            population: Current population working pool
            breeders: List of breeder instances (distributed by config)
            rng: Seeded random number generator
            db_connection: Database connection for persistence
            
        Returns:
            GenerationStats object with calculated metrics
        """
        pass
    
    def advance(self) -> int:
        """Increment generation number and return new value."""
        pass
    
    @property
    def generation_number(self) -> int:
        """Current generation number."""
        pass
```

---

## 7. Implementation Notes

- **In-memory state:** Generation number exists only in memory during simulation
- **Database queries:** Use batch inserts for efficient persistence:
  - Insert one row into `generation_stats` per generation
  - Batch insert all genotype frequencies into `generation_genotype_frequencies` (one row per genotype)
  - Batch insert all trait stats into `generation_trait_stats` (one row per trait, including genotype_diversity)
- **Genotype diversity calculation:** Count distinct genotypes present in the working pool for each trait (number of unique genotype strings with frequency > 0)
- **Statistics calculation:** Perform before creature removal to ensure accuracy
- **Aged-out retrieval:** Use `population.get_aged_out_creatures(current_generation)` to efficiently retrieve creatures who age out (see [Population Model](population.md) for aging-out list details)
- **Breeder distribution:** Distribute breeders according to configuration counts (actual numbers, not percentages)

---

## 8. Database Schema

Generation statistics are stored in normalized tables:

### 8.1 Generation Stats Table

```sql
CREATE TABLE generation_stats (
    simulation_id INTEGER NOT NULL,
    generation INTEGER NOT NULL CHECK(generation >= 0),
    population_size INTEGER NOT NULL CHECK(population_size >= 0),
    eligible_males INTEGER NOT NULL CHECK(eligible_males >= 0),
    eligible_females INTEGER NOT NULL CHECK(eligible_females >= 0),
    births INTEGER NOT NULL CHECK(births >= 0),
    deaths INTEGER NOT NULL CHECK(deaths >= 0),
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
    PRIMARY KEY (simulation_id, generation)
);

CREATE INDEX idx_generation_stats_generation ON generation_stats(simulation_id, generation);
```

### 8.2 Generation Genotype Frequencies Table

```sql
CREATE TABLE generation_genotype_frequencies (
    simulation_id INTEGER NOT NULL,
    generation INTEGER NOT NULL CHECK(generation >= 0),
    trait_id INTEGER NOT NULL CHECK(trait_id >= 0),
    genotype TEXT NOT NULL,
    frequency REAL NOT NULL CHECK(frequency >= 0 AND frequency <= 1),
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
    FOREIGN KEY (simulation_id, generation) REFERENCES generation_stats(simulation_id, generation) ON DELETE CASCADE,
    FOREIGN KEY (trait_id) REFERENCES traits(trait_id) ON DELETE CASCADE,
    PRIMARY KEY (simulation_id, generation, trait_id, genotype)
);

CREATE INDEX idx_genotype_freq_generation ON generation_genotype_frequencies(simulation_id, generation);
CREATE INDEX idx_genotype_freq_trait ON generation_genotype_frequencies(trait_id);
```

### 8.3 Generation Trait Stats Table

```sql
CREATE TABLE generation_trait_stats (
    simulation_id INTEGER NOT NULL,
    generation INTEGER NOT NULL CHECK(generation >= 0),
    trait_id INTEGER NOT NULL CHECK(trait_id >= 0),
    allele_frequencies JSON NOT NULL,  -- Map of allele -> frequency
    heterozygosity REAL NOT NULL CHECK(heterozygosity >= 0 AND heterozygosity <= 1),
    genotype_diversity INTEGER NOT NULL CHECK(genotype_diversity >= 0),  -- Number of distinct genotypes present
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
    FOREIGN KEY (simulation_id, generation) REFERENCES generation_stats(simulation_id, generation) ON DELETE CASCADE,
    FOREIGN KEY (trait_id) REFERENCES traits(trait_id) ON DELETE CASCADE,
    PRIMARY KEY (simulation_id, generation, trait_id)
);

CREATE INDEX idx_trait_stats_generation ON generation_trait_stats(simulation_id, generation);
CREATE INDEX idx_trait_stats_trait ON generation_trait_stats(trait_id);
```

**Note:** Creature persistence details are documented in the [Creature Model](creature.md) section 7.

---

## 9. Relationship to Other Entities

- **Population:** Generation operates on the population working pool (see [Population Model](population.md))
- **Breeder:** Generation uses breeders to select mating pairs (see [Breeder Model](breeder.md))
- **Creature:** Generation coordinates creature lifecycle operations (see [Creature Model](creature.md))
- **Simulation:** Generation is orchestrated by Simulation entity (see [Simulation Model](simulation.md))

---

**Status:** Draft - Ready for review. Next: Simulation Model specification.

