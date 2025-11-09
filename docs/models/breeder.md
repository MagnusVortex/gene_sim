# Breeder Model - Genealogical Simulation

**Document Version:** 1.0  
**Date:** November 8, 2025  
**Status:** Draft - In Progress

---

## 1. Overview

A **Breeder** selects mating pairs from pre-filtered pools of eligible creatures. Different breeder strategies implement different selection criteria (random, inbreeding avoidance, phenotype selection, etc.). Breeders do not handle eligibility filtering—they receive only eligible creatures and focus solely on pair selection.

---

## 2. Core Responsibilities

1. **Select mating pairs** from provided eligible creatures using strategy-specific criteria
2. **Return pairs** for reproduction (offspring created via gamete formation)

**Note:** Eligibility filtering (age limits, litters_remaining, is_alive) is handled by the simulation layer before creatures are passed to the breeder.

---

## 3. Breeder Types

### 3.1 Random Breeder
- Randomly pairs eligible males and females
- No selection bias
- Use case: Baseline, control simulations

### 3.2 Inbreeding Avoidance Breeder
- Calculates inbreeding coefficient for potential offspring using Wright's formula
- Uses parent inbreeding coefficients (from `creature.inbreeding_coefficient`) and relationship coefficient
- Avoids pairs that would produce offspring with high inbreeding coefficient
- Use case: Maintaining genetic diversity

### 3.3 Kennel Club Breeder
- Selects pairs based on target phenotypes from simulation configuration
- Follows guidelines from prestigious kennel clubs (e.g., breed standards, health requirements, lineage restrictions)
- May enforce rules such as: avoiding certain genotype combinations, requiring specific phenotype ranges, limiting inbreeding within guidelines
- Uses same target_phenotypes as unrestricted phenotype breeder (defined at top-level config)
- Use case: Modeling formal breeding programs with established standards

### 3.4 Unrestricted Phenotype Breeder
- Selects pairs based on target phenotypes from simulation configuration
- Follows no guidelines or restrictions
- Purely selects for desired phenotypes without constraints
- Uses same target_phenotypes as kennel club breeder (defined at top-level config)
- Use case: Modeling breeding programs focused solely on phenotype outcomes

---

## 4. Interface

```python
class Breeder:
    def select_pairs(
        self, 
        eligible_males: List[Creature], 
        eligible_females: List[Creature],
        num_pairs: int,
        rng: np.random.Generator
    ) -> List[Tuple[Creature, Creature]]:
        """
        Selects mating pairs from eligible creatures.
        
        Args:
            eligible_males: Pre-filtered list of eligible male creatures
            eligible_females: Pre-filtered list of eligible female creatures
            num_pairs: Number of pairs to select
            rng: Seeded random number generator
            
        Returns:
            List of (male, female) tuples for reproduction
        """
        pass
```

**Note:** Breeders receive pre-filtered eligible creatures. The simulation layer handles eligibility filtering (age limits, litters_remaining, is_alive) before calling the breeder. Breeders focus solely on pair selection strategy.

---

## 5. Implementation Notes

- **Memory-only:** Breeders operate on in-memory working pool (no database queries)
- **Seeded randomness:** All random operations use provided `rng` for reproducibility
- **Pair validation:** Breeders may enforce additional constraints (e.g., no self-pairing, max inbreeding coefficient)
- **Strategy pattern:** Different breeders are interchangeable via configuration
- **Breeder distribution:** The number of breeders of each type is determined by simulation configuration (actual counts, not normalized percentages)

---

## 6. Database Schema

No database schema required. Breeders are runtime strategy objects configured per simulation.

---

**Status:** Draft - Ready for review. Next: Population Model specification.

