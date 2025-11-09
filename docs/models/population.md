# Population Model - Genealogical Simulation

**Document Version:** 1.0  
**Date:** November 8, 2025  
**Status:** Draft - In Progress

---

## 1. Overview

A **Population** represents the working pool of creatures currently in the simulation. It manages creatures in memory, tracking demographic data and providing filtered subsets for breeding operations. Depending on configuration, the working pool may include only creatures able to reproduce, or may persist creatures until they age out.

---

## 2. Core Responsibilities

1. **Maintain working pool** of creatures in memory
2. **Maintain aging-out list** - pre-computed list of creatures who age out in each generation
3. **Filter eligible creatures** for breeding (see [Creature Model](creature.md) section 6 for eligibility criteria)
4. **Get aged-out creatures** for current generation (from pre-computed list)
5. **Track demographic metrics** (size, age distribution, sex ratio)
6. **Calculate genetic diversity** metrics (genotype frequencies, allele frequencies, heterozygosity)
7. **Add new offspring** after reproduction (updates aging-out list)
8. **Remove aged-out creatures** (persists to database before removal - see [Creature Model](creature.md) section 8.3)

---

## 3. Working Pool Management

The population maintains the in-memory working pool of creatures. Removal behavior is controlled by simulation configuration:

- **Inclusion:** Creatures are added to the working pool when:
  - Initial population is created (founders) - **all founders are persisted immediately** and have IDs before being added
  - Offspring are born from reproduction - **all offspring are persisted immediately** when created, but only remaining offspring (not removed) are added to the pool
  
- **Persistence:** **ALL creatures are persisted to the database immediately upon creation:**
  - Founders: Persisted immediately after simulation initialization
  - Offspring: Persisted immediately when created (both removed and remaining)
  - This ensures all creatures have IDs from the start and complete historical records
  
- **Offspring Removal:** Some offspring may be removed before entering the population (sold/given away):
  - Controlled by `offspring_removal_rate` configuration (0.0-1.0 probability)
  - **Removed offspring are still persisted to database immediately** for historical tracking
  - Removed offspring do not enter the breeding pool and do not contribute to population growth
  - This mechanism helps control population growth
  
- **Removal from Working Pool:** Behavior depends on `remove_ineligible_immediately` configuration:
  - **If `true`:** Creatures are removed from working pool immediately after they can no longer reproduce (breeding age limit exceeded or litters_remaining <= 0)
  - **If `false`:** Creatures remain in working pool until they age out
  - **Note:** Since all creatures are already persisted, removal from working pool does NOT involve database writes
  
- **Aging-out list:** Population maintains a pre-computed list/dictionary of creatures who age out in each generation. When a creature is created, its aging-out generation is calculated as `birth_generation + lifespan`, and the creature is added to the list for that generation. This allows efficient retrieval without iterating through all creatures.

- **Updates:** Creature attributes (e.g., `litters_remaining`) are updated in-memory during simulation

---

## 4. Key Metrics

**Demographic:**
- Total population size
- Number of eligible males/females
- Age distribution
- Sex ratio

**Genetic:**
- Genotype frequencies per trait
- Allele frequencies
- Heterozygosity

**Note:** Metrics are calculated on-demand from the working pool. Genotype frequencies are computed before persisting creatures to the database. Phenotype distributions can be calculated post-simulation from persisted data.

---

## 5. Interface

```python
class Population:
    def get_eligible_males(self, current_generation: int, config: SimulationConfig) -> List[Creature]:
        """Returns list of eligible male creatures for breeding."""
        pass
    
    def get_eligible_females(self, current_generation: int, config: SimulationConfig) -> List[Creature]:
        """Returns list of eligible female creatures for breeding."""
        pass
    
    def add_creatures(self, creatures: List[Creature], current_generation: int) -> None:
        """
        Adds new creatures (e.g., remaining offspring after removal) to the working pool.
        Also updates the aging-out list: calculates aging-out generation for each creature
        (birth_generation + lifespan) and adds to the list for that generation.
        
        Note: Creatures added here have already been persisted to the database and have IDs.
        """
        pass
    
    def get_aged_out_creatures(self, current_generation: int) -> List[Creature]:
        """
        Returns list of creatures who age out in the current generation.
        Uses pre-computed aging-out list for efficient retrieval.
        """
        pass
    
    def remove_aged_out_creatures(self, current_generation: int, config: SimulationConfig) -> None:
        """
        Gets aged-out creatures for current generation, persists them to database 
        (see [Creature Model](creature.md) section 8.3), then removes from working pool and aging-out list.
        """
        pass
    
    def calculate_genotype_frequencies(self, trait_id: int) -> Dict[str, float]:
        """Calculates genotype frequencies for a given trait."""
        pass
```

---

## 6. Implementation Notes

- **Memory-only:** Population exists entirely in memory during simulation
- **Efficient filtering:** Use list comprehensions or NumPy arrays for fast eligibility checks (see [Creature Model](creature.md) section 6 for eligibility criteria)
- **Aging-out list:** Maintain a dictionary or list structure keyed by generation number. When creatures are added, calculate their aging-out generation as `birth_generation + lifespan` and add them to the list for that generation. This allows O(1) or O(log n) lookup of creatures who age out in a given generation, rather than O(n) iteration through all creatures.
- **Lazy metrics:** Calculate diversity metrics only when needed (before persistence or on-demand)
- **Batch operations:** Add/remove creatures in batches for efficiency
- **Removal strategy:** Controlled by `remove_ineligible_immediately` simulation configuration flag (see [Creature Model](creature.md) section 8.3)

---

## 7. Database Schema

No direct database schema. Population manages creatures in memory. See [Creature Model](creature.md) section 7 for database schema details.

---

**Status:** Draft - Ready for review. Next: Generation Model specification.

