# Database Schema Overview - Genealogical Simulation

**Document Version:** 1.0  
**Date:** November 8, 2025  
**Status:** Complete

---

## 1. Overview

This document provides a comprehensive overview of the SQLite database schema for the genealogical simulation system. All tables, relationships, indexes, and constraints are documented here. For detailed field descriptions and design notes, see the individual model documents.

---

## 2. Table Summary

| Table | Purpose | Primary Key | Detailed Schema |
|-------|---------|-------------|-----------------|
| `simulations` | Simulation metadata and lifecycle tracking | `simulation_id` | [Simulation Model](models/simulation.md#511-simulations-table) |
| `traits` | Trait definitions (genetic characteristics) | `trait_id` | [Trait Model](models/trait.md#7-database-schema-sqlite) |
| `genotypes` | Genotype definitions with phenotype mappings | `genotype_id` | [Trait Model](models/trait.md#7-database-schema-sqlite) |
| `creatures` | Individual creature records and lineage | `creature_id` | [Creature Model](models/creature.md#71-creatures-table) |
| `creature_genotypes` | Genotypes for each trait per creature | `(creature_id, trait_id)` | [Creature Model](models/creature.md#72-genotypes-table-creature-genotypes) |
| `generation_stats` | Demographic statistics per generation | `(simulation_id, generation)` | [Generation Model](models/generation.md#81-generation-stats-table) |
| `generation_genotype_frequencies` | Genotype frequencies per generation | `(simulation_id, generation, trait_id, genotype)` | [Generation Model](models/generation.md#82-generation-genotype-frequencies-table) |
| `generation_trait_stats` | Allele frequencies and heterozygosity per generation | `(simulation_id, generation, trait_id)` | [Generation Model](models/generation.md#83-generation-trait-stats-table) |

---

## 3. Complete Schema

### 3.1 Simulations Table

```sql
CREATE TABLE simulations (
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
);

CREATE INDEX idx_simulations_status ON simulations(status);
CREATE INDEX idx_simulations_seed ON simulations(seed);
CREATE INDEX idx_simulations_created ON simulations(created_at);
```

### 3.2 Traits Table

```sql
CREATE TABLE traits (
    trait_id INTEGER PRIMARY KEY CHECK(trait_id >= 0 AND trait_id < 100),
    name TEXT NOT NULL,
    trait_type TEXT NOT NULL CHECK(trait_type IN (
        'SIMPLE_MENDELIAN', 
        'INCOMPLETE_DOMINANCE', 
        'CODOMINANCE', 
        'SEX_LINKED', 
        'POLYGENIC'
    ))
);

CREATE INDEX idx_traits_type ON traits(trait_type);
```

### 3.3 Genotypes Table

```sql
CREATE TABLE genotypes (
    genotype_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trait_id INTEGER NOT NULL,
    genotype TEXT NOT NULL,
    phenotype TEXT NOT NULL,
    sex TEXT,
    initial_freq REAL NOT NULL CHECK(initial_freq >= 0.0 AND initial_freq <= 1.0),
    FOREIGN KEY (trait_id) REFERENCES traits(trait_id) ON DELETE CASCADE,
    UNIQUE(trait_id, genotype, sex)
);

CREATE INDEX idx_genotypes_trait ON genotypes(trait_id);
CREATE INDEX idx_genotypes_phenotype ON genotypes(trait_id, phenotype);
```

### 3.4 Creatures Table

```sql
CREATE TABLE creatures (
    creature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id INTEGER NOT NULL,
    birth_generation INTEGER NOT NULL CHECK(birth_generation >= 0),
    sex TEXT CHECK(sex IN ('male', 'female')) NULL,
    parent1_id INTEGER NULL,
    parent2_id INTEGER NULL,
    litters_remaining INTEGER NOT NULL CHECK(litters_remaining >= 0),
    lifespan INTEGER NOT NULL CHECK(lifespan > 0),
    is_alive BOOLEAN DEFAULT 1,
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
    FOREIGN KEY (parent1_id) REFERENCES creatures(creature_id) ON DELETE SET NULL,
    FOREIGN KEY (parent2_id) REFERENCES creatures(creature_id) ON DELETE SET NULL,
    CHECK(parent1_id IS NULL = (birth_generation = 0)),
    CHECK(parent2_id IS NULL = (birth_generation = 0))
);

CREATE INDEX idx_creatures_birth_generation ON creatures(simulation_id, birth_generation);
CREATE INDEX idx_creatures_parents ON creatures(parent1_id, parent2_id);
CREATE INDEX idx_creatures_breeding_eligibility ON creatures(simulation_id, sex, birth_generation, litters_remaining, is_alive);
```

### 3.5 Creature Genotypes Table

```sql
CREATE TABLE creature_genotypes (
    creature_id INTEGER NOT NULL,
    trait_id INTEGER NOT NULL CHECK(trait_id >= 0),
    genotype TEXT NOT NULL,
    FOREIGN KEY (creature_id) REFERENCES creatures(creature_id) ON DELETE CASCADE,
    FOREIGN KEY (trait_id) REFERENCES traits(trait_id) ON DELETE CASCADE,
    PRIMARY KEY (creature_id, trait_id)
);

CREATE INDEX idx_creature_genotypes_trait ON creature_genotypes(trait_id);
CREATE INDEX idx_creature_genotypes_genotype ON creature_genotypes(genotype);
CREATE INDEX idx_creature_genotypes_creature ON creature_genotypes(creature_id);
```

### 3.6 Generation Stats Table

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

### 3.7 Generation Genotype Frequencies Table

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

### 3.8 Generation Trait Stats Table

```sql
CREATE TABLE generation_trait_stats (
    simulation_id INTEGER NOT NULL,
    generation INTEGER NOT NULL CHECK(generation >= 0),
    trait_id INTEGER NOT NULL CHECK(trait_id >= 0),
    allele_frequencies JSON NOT NULL,
    heterozygosity REAL NOT NULL CHECK(heterozygosity >= 0 AND heterozygosity <= 1),
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
    FOREIGN KEY (simulation_id, generation) REFERENCES generation_stats(simulation_id, generation) ON DELETE CASCADE,
    FOREIGN KEY (trait_id) REFERENCES traits(trait_id) ON DELETE CASCADE,
    PRIMARY KEY (simulation_id, generation, trait_id)
);

CREATE INDEX idx_trait_stats_generation ON generation_trait_stats(simulation_id, generation);
CREATE INDEX idx_trait_stats_trait ON generation_trait_stats(trait_id);
```

---

## 4. Foreign Key Relationships

```
simulations (1) ──< (many) creatures
simulations (1) ──< (many) generation_stats
simulations (1) ──< (many) generation_genotype_frequencies
simulations (1) ──< (many) generation_trait_stats

traits (1) ──< (many) genotypes
traits (1) ──< (many) creature_genotypes
traits (1) ──< (many) generation_genotype_frequencies
traits (1) ──< (many) generation_trait_stats

creatures (1) ──< (many) creature_genotypes
creatures (1) ──< (many) creatures (via parent1_id, parent2_id)

generation_stats (1) ──< (many) generation_genotype_frequencies
generation_stats (1) ──< (many) generation_trait_stats
```

**Relationship Details:**
- **simulations → creatures**: One simulation has many creatures (ON DELETE CASCADE)
- **simulations → generation_stats**: One simulation has many generation statistics (ON DELETE CASCADE)
- **traits → genotypes**: One trait has many possible genotypes (ON DELETE CASCADE)
- **traits → creature_genotypes**: One trait appears in many creature genotypes (ON DELETE CASCADE)
- **creatures → creature_genotypes**: One creature has genotypes for many traits (ON DELETE CASCADE)
- **creatures → creatures**: Self-referential for lineage (parent1_id, parent2_id) (ON DELETE SET NULL)
- **generation_stats → generation_genotype_frequencies**: One generation has many genotype frequencies (ON DELETE CASCADE)
- **generation_stats → generation_trait_stats**: One generation has trait stats for many traits (ON DELETE CASCADE)

---

## 5. Index Summary

### 5.1 Simulations Indexes
- `idx_simulations_status` - Query simulations by status
- `idx_simulations_seed` - Query simulations by seed (for reproducibility checks)
- `idx_simulations_created` - Query simulations by creation date

### 5.2 Traits Indexes
- `idx_traits_type` - Query traits by type

### 5.3 Genotypes Indexes
- `idx_genotypes_trait` - Query genotypes by trait
- `idx_genotypes_phenotype` - Query genotypes by phenotype within trait

### 5.4 Creatures Indexes
- `idx_creatures_birth_generation` - Query creatures by simulation and birth generation (time-series queries)
- `idx_creatures_parents` - Query creatures by parent relationships (lineage queries)
- `idx_creatures_breeding_eligibility` - Query eligible breeders (composite index for filtering)

### 5.5 Creature Genotypes Indexes
- `idx_creature_genotypes_trait` - Query creature genotypes by trait
- `idx_creature_genotypes_genotype` - Query creatures by specific genotype
- `idx_creature_genotypes_creature` - Query all genotypes for a creature

### 5.6 Generation Stats Indexes
- `idx_generation_stats_generation` - Query generation stats by simulation and generation

### 5.7 Generation Genotype Frequencies Indexes
- `idx_genotype_freq_generation` - Query genotype frequencies by generation
- `idx_genotype_freq_trait` - Query genotype frequencies by trait (across generations)

### 5.8 Generation Trait Stats Indexes
- `idx_trait_stats_generation` - Query trait stats by generation
- `idx_trait_stats_trait` - Query trait stats by trait (across generations)

---

## 6. Data Flow

### 6.1 Simulation Initialization
1. Insert into `simulations` table (status='pending')
2. Insert trait definitions into `traits` table
3. Insert genotype definitions into `genotypes` table
4. Create initial population in `creatures` table
5. Insert creature genotypes into `creature_genotypes` table

### 6.2 Generation Cycle
1. Update `simulations.status` to 'running' (if first generation)
2. Create offspring, insert into `creatures` and `creature_genotypes`
3. Persist aged-out creatures to `creatures` and `creature_genotypes`
4. Calculate statistics, insert into:
   - `generation_stats`
   - `generation_genotype_frequencies`
   - `generation_trait_stats`
5. Update `simulations.generations_completed`

### 6.3 Simulation Completion
1. Update `simulations.status` to 'completed'
2. Update `simulations.end_time` and `final_population_size`
3. Update `simulations.updated_at`

---

## 7. Query Patterns

### 7.1 Time-Series Queries
```sql
-- Trait frequency over generations
SELECT generation, frequency 
FROM generation_genotype_frequencies
WHERE simulation_id = ? AND trait_id = ? AND genotype = ?
ORDER BY generation;

-- Population size over time
SELECT generation, population_size
FROM generation_stats
WHERE simulation_id = ?
ORDER BY generation;
```

### 7.2 Lineage Queries
```sql
-- Get all descendants of a creature
WITH RECURSIVE descendants AS (
    SELECT creature_id FROM creatures WHERE creature_id = ?
    UNION
    SELECT c.creature_id FROM creatures c
    INNER JOIN descendants d ON c.parent1_id = d.creature_id OR c.parent2_id = d.creature_id
)
SELECT * FROM descendants;

-- Get all ancestors of a creature
WITH RECURSIVE ancestors AS (
    SELECT creature_id, parent1_id, parent2_id FROM creatures WHERE creature_id = ?
    UNION
    SELECT c.creature_id, c.parent1_id, c.parent2_id FROM creatures c
    INNER JOIN ancestors a ON c.creature_id = a.parent1_id OR c.creature_id = a.parent2_id
)
SELECT * FROM ancestors;
```

### 7.3 Trait Analysis Queries
```sql
-- Genotype distribution for a trait at a specific generation
SELECT genotype, frequency
FROM generation_genotype_frequencies
WHERE simulation_id = ? AND generation = ? AND trait_id = ?
ORDER BY frequency DESC;

-- Allele frequencies and heterozygosity over time
SELECT generation, allele_frequencies, heterozygosity
FROM generation_trait_stats
WHERE simulation_id = ? AND trait_id = ?
ORDER BY generation;
```

---

## 8. Design Principles

### 8.1 Normalization
- Genotype frequencies normalized: one row per genotype per generation
- Trait stats normalized: one row per trait per generation
- Creature genotypes normalized: one row per trait per creature

### 8.2 Referential Integrity
- Foreign keys enforce relationships
- ON DELETE CASCADE ensures cleanup when simulations are deleted
- ON DELETE SET NULL for parent references (preserves lineage even if parent deleted)

### 8.3 Performance Optimization
- Indexes on common query patterns (generation, trait_id, simulation_id)
- Composite indexes for multi-column filters
- Normalized structure enables efficient aggregations

### 8.4 Data Integrity
- CHECK constraints validate data ranges
- UNIQUE constraints prevent duplicates
- Foreign keys ensure referential integrity

---

## 9. References

- **Simulations Table**: [Simulation Model](models/simulation.md#511-simulations-table)
- **Traits & Genotypes Tables**: [Trait Model](models/trait.md#7-database-schema-sqlite)
- **Creatures & Creature Genotypes Tables**: [Creature Model](models/creature.md#7-database-schema-sqlite)
- **Generation Statistics Tables**: [Generation Model](models/generation.md#8-database-schema)

---

**Status:** Complete - Ready for implementation

