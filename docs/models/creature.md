# Creature Model - Genealogical Simulation

**Document Version:** 1.0  
**Date:** November 8, 2025  
**Status:** Draft - In Progress

---

## 1. Overview

A **Creature** represents an individual organism in the simulation with a diploid genome, expressed traits (phenotypes), and lineage information. Creatures are the fundamental unit of the simulation - they reproduce, inherit genetic material, and persist across multiple generations (mutations in Phase 2).

---

## 2. Core Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `creature_id` | Integer | Unique identifier for the creature (auto-increment primary key) |
| `simulation_id` | Integer | Foreign key to simulation this creature belongs to |
| `birth_generation` | Integer | Generation when creature was born (fixed, never changes) |
| `sex` | Enum | Biological sex: 'male', 'female', or NULL (if sex not modeled) |
| `parent1_id` | Integer | Foreign key to first parent (NULL for founders) |
| `parent2_id` | Integer | Foreign key to second parent (NULL for founders) |
| `inbreeding_coefficient` | Real | Inbreeding coefficient (F) for this creature, calculated from pedigree (0.0 to 1.0) |
| `litters_remaining` | Integer | Number of litters remaining for this creature (starts at max value from simulation config, decrements per litter) |
| `lifespan` | Integer | Individual lifespan for this creature (sampled from lifespan range in simulation config at birth) |
| `is_alive` | Boolean | Whether creature is alive in current generation (for mortality modeling) |

**Design Notes:**
- **CRITICAL: All creatures are persisted to the database immediately upon creation** (see section 8.3)
- Creatures persist across generations (they don't die automatically each generation)
- `creature_id`: Assigned immediately when creature is persisted (all creatures are persisted upon creation)
- `birth_generation`: Fixed timestamp of when creature was born (persisted immediately when creature is created)
- `lifespan`: Individual lifespan sampled from config range at creation (fixed, never changes)
- `inbreeding_coefficient`: Calculated when creature is created using Wright's formula: `F_offspring = (1/2) × (1 + F_parent1) × (1 + F_parent2) × r_parents`. Founders have F = 0.0. Stored as REAL value between 0.0 and 1.0.
- Age calculation: `age = current_generation - birth_generation` (calculated on-demand, not stored)
- Creatures age out when `age >= lifespan` (where `age = current_generation - birth_generation`)
- Creatures have diploid genomes (two alleles per gene)
- Genome stored as array: `genome[trait_id] = genotype_string` (e.g., "BB", "Bb", "bb")
- Phenotypes derived from genotypes via trait configuration
- Lineage tracked via parent references (enables forward/backward traversal)
- Breeding eligibility: Age limit and litters_remaining limit defined at simulation level

**Key Distinction: `birth_generation` vs `current_generation`**
- **`birth_generation`**: Fixed generation when creature was born. Persisted immediately when creature is created (all creatures are persisted immediately). Used to calculate age: `age = current_generation - birth_generation`.
- **`current_generation`**: Runtime simulation state (in-memory only, not persisted). Increments each breeding cycle.

---

## 3. Genome Representation

### 3.1 Diploid Structure

Each creature has a diploid genome - two copies of each chromosome/gene. For each trait, the creature has a genotype (allele combination).

**Genome Storage:**
- In-memory: NumPy array or Python dict: `genome[trait_id] = genotype_string`
- In database: Separate table with one row per trait per creature (normalized) - written when creature is persisted

**Example Genome:**
```python
creature.genome = {
    0: "BB",      # Trait 0 (Eye Color): homozygous dominant
    1: "RW",      # Trait 1 (Flower Color): heterozygous (incomplete dominance)
    2: "AB",      # Trait 2 (Blood Type): codominant
    3: "Nc",      # Trait 3 (Color Blindness): sex-linked, female carrier
    4: "H1H1_H2H2_H3h3"  # Trait 4 (Height): polygenic
}
```

### 3.2 Genotype Format

Genotypes are stored as strings matching the format defined in trait configuration:
- **Simple Mendelian:** "BB", "Bb", "bb" (two alleles)
- **Incomplete Dominance:** "RR", "RW", "WW" (two alleles)
- **Codominance:** "AA", "AO", "BB", "BO", "AB", "OO" (two alleles)
- **Sex-Linked:** "NN", "Nc", "cc" (females) or "N", "c" (males - single allele)
- **Polygenic:** "L1L1_L2L2_L3L3" (multiple genes, underscore-separated)

---

## 4. Lineage & Pedigree

### 4.1 Parent-Child Relationships

Each creature (except founders) has exactly two parents:
- `parent1_id`: Reference to first parent
- `parent2_id`: Reference to second parent
- Both parents must exist in the working pool (memory) and be alive at time of reproduction

**Founders (Birth Generation 0):**
- `parent1_id = NULL`
- `parent2_id = NULL`
- Created at simulation initialization with genotypes sampled from initial frequencies
- `birth_generation = 0`

### 4.2 Inbreeding Coefficient

The inbreeding coefficient (F) is calculated when a creature is created using Wright's formula:
- **Founders:** F = 0.0 (no inbreeding)
- **Offspring:** F = (1/2) × (1 + F_parent1) × (1 + F_parent2) × r_parents
  - Where `r_parents` is the coefficient of relationship between the parents
  - Parent inbreeding coefficients compound multiplicatively with the relationship coefficient
- Stored in `inbreeding_coefficient` field (REAL, 0.0 to 1.0)
- Used by inbreeding avoidance breeders to select mating pairs
- Can be queried for analysis of inbreeding trends over generations

#### 4.2.1 Relationship Coefficient Calculation

The coefficient of relationship (`r_parents`) measures the probability that two individuals share identical alleles by descent from common ancestors. It is calculated by traversing the pedigree to find common ancestors.

**Calculation Method:**
1. **Find common ancestors:** Traverse both parent pedigrees to identify shared ancestors
2. **Calculate paths:** For each common ancestor, find all paths connecting the two parents through that ancestor
3. **Sum contributions:** For each path, calculate `(1/2)^(n1 + n2 + 1)` where:
   - `n1` = number of generations from parent1 to common ancestor
   - `n2` = number of generations from parent2 to common ancestor
4. **Account for inbreeding:** Multiply each path contribution by `(1 + F_common_ancestor)` if the common ancestor is inbred
5. **Sum all paths:** `r_parents` = sum of all path contributions

**Common Relationship Values (for reference):**
- **Unrelated:** r = 0.0 (no common ancestors)
- **Parent-Offspring:** r = 0.5 (direct relationship)
- **Full Siblings:** r = 0.5 (share both parents)
- **Half Siblings:** r = 0.25 (share one parent)
- **First Cousins:** r = 0.125 (share grandparents)
- **Uncle-Niece/Aunt-Nephew:** r = 0.25 (one generation difference)

**Implementation Note:** For Phase 1, a simplified implementation may use a lookup table for common relationships or calculate r by traversing the pedigree up to a limited depth (e.g., 5-10 generations). Full pedigree traversal can be implemented if needed for complex pedigrees.

---

## 5. Reproduction & Inheritance

### 5.1 Gamete Formation

When a creature reproduces, it produces gametes (sperm/egg) containing one allele per gene.

**Process:**
1. For each trait, randomly select one allele from the diploid pair
2. Use seeded pRNG: `rng.choice([allele1, allele2])`
3. Combine gametes from two parents to form offspring genotype

**Example - Simple Mendelian:**
```python
# Parent 1: "Bb" → gamete: randomly "B" or "b"
# Parent 2: "BB" → gamete: always "B"
# Offspring: "BB" or "Bb" (50/50 chance)
```

### 5.2 Independent Assortment

Genes on different chromosomes assort independently (Mendel's Law of Independent Assortment).

**Implementation:**
- Each trait's gamete selection is independent
- No linkage modeled in Phase 1 (future: linkage groups)

### 5.3 Sex-Linked Inheritance

For sex-linked traits, inheritance depends on parent sex:
- **X-linked (most common):**
  - Female parent: Contributes one X chromosome allele (random selection)
  - Male parent: Contributes X chromosome allele (only has one)
  - Offspring sex determines genotype format (male = single allele, female = two alleles)

**Example:**
```python
# Color blindness (X-linked recessive)
# Female parent: "Nc" → gamete: "N" or "c" (50/50)
# Male parent: "N" → gamete: "N"
# Offspring:
#   - If female: "NN" or "Nc" (50/50)
#   - If male: "N" (always, since father contributes X)
```

---

## 6. Breeding Eligibility & Limits

### 6.1 Age-Based Limits

Creatures can be excluded from breeding based on their age (number of generations since birth).

**Age Calculation:**
```python
age = current_simulation_generation - creature.birth_generation
```
Age is calculated on-demand when needed, not stored as a mutable field.

**Age Limit:**
- Defined at simulation level (creature archetype configuration)
- Applies to **both males and females**
- If `age > max_age`, creature is not eligible for breeding
- Separate age limits can be configured for males and females

### 6.2 Litters Remaining Limits

Creatures can be excluded from breeding based on how many litters they have remaining.

**Litter Tracking:**
- `litters_remaining`: Integer counter, starts at the maximum value defined in simulation configuration
- Decrements by 1 each time creature produces a litter
- Only applies to **females** (males don't produce litters)
- Updated when female reproduces

**Litter Limit:**
- Defined at simulation level (creature archetype configuration)
- Only applies to **females**
- If `litters_remaining <= 0`, female is not eligible for breeding
- Males have no litter limit (unless specified in simulation config)

**Design Note:** These limits are part of the creature archetype defined in the simulation configuration, allowing different species/life histories to be modeled.

---

## 7. Database Schema (SQLite)

### 7.1 Creatures Table

```sql
-- Creatures Table
-- Stores basic creature information and lineage
CREATE TABLE creatures (
    creature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id INTEGER NOT NULL,
    birth_generation INTEGER NOT NULL CHECK(birth_generation >= 0),
    sex TEXT CHECK(sex IN ('male', 'female')) NULL,
    parent1_id INTEGER NULL,
    parent2_id INTEGER NULL,
    inbreeding_coefficient REAL NOT NULL CHECK(inbreeding_coefficient >= 0.0 AND inbreeding_coefficient <= 1.0) DEFAULT 0.0,
    litters_remaining INTEGER NOT NULL CHECK(litters_remaining >= 0),
    lifespan INTEGER NOT NULL CHECK(lifespan > 0),
    is_alive BOOLEAN DEFAULT 1,
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
    FOREIGN KEY (parent1_id) REFERENCES creatures(creature_id) ON DELETE SET NULL,
    FOREIGN KEY (parent2_id) REFERENCES creatures(creature_id) ON DELETE SET NULL,
    CHECK(parent1_id IS NULL = (birth_generation = 0)),  -- Founders have no parents
    CHECK(parent2_id IS NULL = (birth_generation = 0))
);

-- Indexes for efficient querying
CREATE INDEX idx_creatures_birth_generation ON creatures(simulation_id, birth_generation);
CREATE INDEX idx_creatures_parents ON creatures(parent1_id, parent2_id);
CREATE INDEX idx_creatures_breeding_eligibility ON creatures(simulation_id, sex, birth_generation, litters_remaining, is_alive);
CREATE INDEX idx_creatures_inbreeding ON creatures(simulation_id, inbreeding_coefficient);
```

### 7.2 Genotypes Table (Creature Genotypes)

```sql
-- Creature Genotypes Table
-- Stores genotype for each trait for each creature (normalized: one row per trait per creature)
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

**Design Notes:**
- Normalized approach: one row per trait per creature
- Better query performance (indexed trait_id and genotype)
- Easier to query "all creatures with genotype X for trait Y"
- Supports efficient aggregation queries
- More rows than denormalized approach, but SQLite handles this well

### 7.3 Example Data

```sql
-- Example: Persisting creatures to database after they can no longer reproduce
-- Founder creature (birth_generation 0) - persisted after becoming ineligible
INSERT INTO creatures (simulation_id, birth_generation, sex, parent1_id, parent2_id, litters_remaining, lifespan)
VALUES (1, 0, 'male', NULL, NULL, 0, 15);  -- lifespan sampled from config range at birth

INSERT INTO creature_genotypes (creature_id, trait_id, genotype) VALUES
(1, 0, 'BB'),  -- Eye Color: Brown
(1, 1, 'RR'),  -- Flower Color: Red
(1, 2, 'AA');  -- Blood Type: A

-- Offspring creature (birth_generation 1) - persisted after litters_remaining reached 0
INSERT INTO creatures (simulation_id, birth_generation, sex, parent1_id, parent2_id, litters_remaining, lifespan)
VALUES (1, 1, 'female', 1, 2, 0, 17);  -- litters_remaining = 0 when persisted, lifespan sampled from config range at birth

INSERT INTO creature_genotypes (creature_id, trait_id, genotype) VALUES
(2, 0, 'Bb'),  -- Eye Color: Brown (heterozygous)
(2, 1, 'RW'),  -- Flower Color: Pink (incomplete dominance)
(2, 2, 'AO');  -- Blood Type: A (heterozygous)

-- Note: During simulation, litters_remaining is decremented in memory.
-- The database reflects the final state when the creature is persisted.
```

---

## 8. Performance Considerations

### 8.1 Batch Operations

When persisting creatures to the database (after they can no longer reproduce):
- Use batch INSERT statements for efficient writes
- Insert creatures first, then genotypes in separate batch
- Use transactions for atomicity

```python
# Example batch insert when persisting creatures that are no longer relevant
creatures_data = [(sim_id, birth_gen, sex, p1, p2, litters_remaining) for ...]  # Creatures being removed from working pool
cursor.executemany(
    "INSERT INTO creatures (simulation_id, birth_generation, sex, parent1_id, parent2_id, litters_remaining) VALUES (?, ?, ?, ?, ?, ?)",
    creatures_data
)

genotypes_data = [(creature_id, trait_id, genotype) for ...]
cursor.executemany(
    "INSERT INTO creature_genotypes (creature_id, trait_id, genotype) VALUES (?, ?, ?)",
    genotypes_data
)
```

### 8.2 Query Optimization

**Note:** These indexes are for querying historical data from the database after creatures have been persisted. During simulation, creatures are accessed directly from the in-memory working pool.

**Creatures Table Indexes:**
- `idx_creatures_birth_generation` on (simulation_id, birth_generation) for time-series queries on historical data
- `idx_creatures_parents` on (parent1_id, parent2_id) for lineage queries on persisted creatures
- `idx_creatures_breeding_eligibility` on (simulation_id, sex, birth_generation, litters_remaining, is_alive) for analyzing breeding patterns in historical data

**Creature Genotypes Table Indexes:**
- `idx_creature_genotypes_trait` on (trait_id) for trait-based queries on historical data
- `idx_creature_genotypes_genotype` on (genotype) for genotype frequency analysis
- `idx_creature_genotypes_creature` on (creature_id) for retrieving complete genomes of persisted creatures

- Use EXPLAIN QUERY PLAN to verify index usage when querying historical data

### 8.3 Persistence Strategy

**CRITICAL: All creatures are persisted to the database immediately upon creation.**

This is a fundamental design principle: every creature is written to the database the moment it is created, ensuring all creatures have IDs from the start. This simplifies parent ID tracking and ensures complete historical records.

**Persistence Timeline:**

1. **Founders (Generation 0):**
   - Created during simulation initialization
   - Persisted immediately after simulation record creation (before any breeding occurs)
   - All founders have `creature_id` assigned before generation 1 begins

2. **Offspring (Generation 1+):**
   - Created during reproduction cycle
   - **All offspring are persisted immediately** when created, before any further processing:
     - **Removed offspring** (sold/given away): Persisted immediately but do not enter the breeding pool
     - **Remaining offspring**: Persisted immediately before being added to the population
   - All offspring have `creature_id` assigned before being used as parents in future generations

**Working Pool Removal** (creatures removed from in-memory pool):
- Since all creatures are already persisted, removal from the working pool does NOT involve database writes
- Removal timing is controlled by `remove_ineligible_immediately` simulation configuration:
  - **If `true`:** Creatures are removed from working pool immediately after they can no longer reproduce (breeding age limit exceeded or `litters_remaining <= 0`)
  - **If `false`:** Creatures remain in working pool until they age out (`age >= lifespan`), then are removed
- Aged-out creatures are removed from the working pool (they are already in the database)

**Persistence Process** (handled by Population):
1. Creatures are inserted into `creatures` table with auto-increment `creature_id`
2. Genotypes are inserted into `creature_genotypes` table (one row per trait)
3. `creature_id` is assigned to the creature object immediately
4. Database transaction is committed

**Key Benefits:**
- All creatures have IDs from creation, simplifying parent ID tracking
- Complete historical records (even removed offspring are in database)
- No risk of losing creature data if simulation crashes
- Parent IDs can always be set correctly since parents are already persisted

**Note:** See [Population Model](population.md) for working pool management details.

---

## 9. Validation Rules

When creating or updating creatures:

1. **Birth Generation Consistency:**
   - Founders: birth_generation = 0, parent1_id = NULL, parent2_id = NULL
   - Offspring: birth_generation > 0, both parents must exist in the working pool (memory) and be alive

2. **Genotype Validity:**
   - Genotype string must match format defined in trait configuration
   - For sex-linked traits, genotype format must match creature's sex
   - All traits must have genotypes (no NULL genotypes)

3. **Sex-Linked Constraints:**
   - Sex-linked trait genotypes must match sex:
     - Female: Two alleles (e.g., "NN", "Nc", "cc")
     - Male: Single allele (e.g., "N", "c")

4. **Litters Remaining:**
   - Must be >= 0
   - Decrements when female reproduces
   - Starts at maximum value defined in simulation configuration
   - Only applies to females (males can have 0, but it's not used)

5. **Parent Validation:**
   - parent1_id and parent2_id must be different (no self-fertilization)
   - Parents must exist in the working pool (memory) and be alive
   - Parents' birth_generation must be < offspring's birth_generation

6. **Breeding Eligibility:**
   - **For Females:**
     - Age check: `current_generation - birth_generation <= max_female_age` 
       - `current_generation` is from memory (simulation state)
       - `birth_generation` is from memory (creature attribute in working pool)
       - `max_female_age` is from simulation config
     - Litter check: `litters_remaining > 0` (creature attribute in working pool)
     - Both checks must pass for female to be eligible
   - **For Males:**
     - Age check: `current_generation - birth_generation <= max_male_age` 
       - `current_generation` is from memory (simulation state)
       - `birth_generation` is from memory (creature attribute in working pool)
       - `max_male_age` is from simulation config

---

**Status:** Draft - Ready for review. Next: Breeder Model specification.
