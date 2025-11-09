"""Creature model for gene_sim."""

from typing import List, Optional, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from .trait import Trait
    from ..config import SimulationConfig


class Creature:
    """Represents an individual creature with genome, lineage, and lifecycle attributes."""
    
    def __init__(
        self,
        simulation_id: int,
        birth_generation: int,
        sex: Optional[str],
        genome: List[Optional[str]],  # List indexed by trait_id, None for unset traits
        parent1_id: Optional[int] = None,
        parent2_id: Optional[int] = None,
        inbreeding_coefficient: float = 0.0,
        litters_remaining: int = 0,
        lifespan: int = 1,
        is_alive: bool = True,
        creature_id: Optional[int] = None
    ):
        """
        Initialize a creature.
        
        Args:
            simulation_id: ID of simulation this creature belongs to
            birth_generation: Generation when creature was born
            sex: 'male', 'female', or None
            genome: List of genotype strings indexed by trait_id (0-99)
            parent1_id: ID of first parent (None for founders)
            parent2_id: ID of second parent (None for founders)
            inbreeding_coefficient: Inbreeding coefficient (F) for this creature
            litters_remaining: Number of litters remaining (for females)
            lifespan: Individual lifespan in generations
            is_alive: Whether creature is alive
            creature_id: Optional ID (assigned when persisted to database)
        """
        self.simulation_id = simulation_id
        self.birth_generation = birth_generation
        self.sex = sex
        self.genome = genome  # List[str] indexed by trait_id
        self.parent1_id = parent1_id
        self.parent2_id = parent2_id
        self.inbreeding_coefficient = inbreeding_coefficient
        self.litters_remaining = litters_remaining
        self.lifespan = lifespan
        self.is_alive = is_alive
        self.creature_id = creature_id
        
        # Validate founders have no parents
        if birth_generation == 0:
            if parent1_id is not None or parent2_id is not None:
                raise ValueError("Founders (birth_generation=0) must have no parents")
        else:
            # For offspring, parent IDs can be None initially (in-memory creatures)
            # They will be set when parents are persisted to database
            if parent1_id == parent2_id and parent1_id is not None:
                raise ValueError("Creature cannot be its own parent")
        
        if not (0.0 <= inbreeding_coefficient <= 1.0):
            raise ValueError(f"inbreeding_coefficient must be between 0.0 and 1.0, got {inbreeding_coefficient}")
    
    def calculate_age(self, current_generation: int) -> int:
        """
        Calculate creature's age in generations.
        
        Args:
            current_generation: Current simulation generation
            
        Returns:
            Age in generations
        """
        return current_generation - self.birth_generation
    
    def is_breeding_eligible(self, current_generation: int, config: 'SimulationConfig') -> bool:
        """
        Check if creature is eligible for breeding.
        
        Args:
            current_generation: Current simulation generation
            config: Simulation configuration
            
        Returns:
            True if eligible, False otherwise
        """
        if not self.is_alive:
            return False
        
        age = self.calculate_age(current_generation)
        
        # Check age limit
        if self.sex == 'male':
            max_age = config.creature_archetype.max_breeding_age_male
        elif self.sex == 'female':
            max_age = config.creature_archetype.max_breeding_age_female
        else:
            # No sex specified, use male limit as default
            max_age = config.creature_archetype.max_breeding_age_male
        
        if age > max_age:
            return False
        
        # Check litter limit (only for females)
        if self.sex == 'female' and self.litters_remaining <= 0:
            return False
        
        return True
    
    def produce_gamete(self, trait_id: int, trait: 'Trait', rng: np.random.Generator) -> str:
        """
        Produce a gamete (single allele) for a given trait.
        
        Args:
            trait_id: ID of the trait
            trait: Trait object with genotype information
            rng: Random number generator
            
        Returns:
            Single allele string for the gamete
        """
        genotype_str = self.genome[trait_id]
        if genotype_str is None:
            raise ValueError(f"Creature has no genotype for trait {trait_id}")
        
        # Handle sex-linked traits differently
        if trait.trait_type.value == 'SEX_LINKED':
            if self.sex == 'male':
                # Males have single allele (X chromosome)
                return genotype_str  # Already single allele
            else:
                # Females have two alleles, randomly select one
                if len(genotype_str) == 2:
                    return rng.choice(list(genotype_str))
                else:
                    # Handle multi-character genotypes (e.g., "Nc")
                    alleles = list(genotype_str)
                    return rng.choice(alleles)
        else:
            # Non-sex-linked: extract alleles from genotype string
            # For simple genotypes like "BB", "Bb", extract individual alleles
            # For polygenic like "H1H1_H2H2_H3H3", extract pairs
            
            if '_' in genotype_str:
                # Polygenic: select one allele from each gene pair
                gene_pairs = genotype_str.split('_')
                selected = []
                for pair in gene_pairs:
                    if len(pair) >= 2:
                        # Extract alleles (e.g., "H1H1" -> ["H1", "H1"])
                        allele1 = pair[:len(pair)//2]
                        allele2 = pair[len(pair)//2:]
                        selected.append(rng.choice([allele1, allele2]))
                return '_'.join(selected)
            else:
                # Simple genotype: extract two alleles
                if len(genotype_str) == 2:
                    return rng.choice(list(genotype_str))
                else:
                    # Handle longer genotypes (e.g., codominance "AB")
                    mid = len(genotype_str) // 2
                    allele1 = genotype_str[:mid]
                    allele2 = genotype_str[mid:]
                    return rng.choice([allele1, allele2])
    
    @staticmethod
    def calculate_relationship_coefficient(
        parent1: 'Creature',
        parent2: 'Creature'
    ) -> float:
        """
        Calculate coefficient of relationship (r) between two creatures.
        
        Simplified Phase 1 implementation:
        - Unrelated: r = 0.0
        - Siblings: r = 0.5 (share both parents)
        - Parent-offspring: r = 0.5 (one is parent of other)
        - Half-siblings: r = 0.25 (share one parent)
        - First cousins: r = 0.125 (traverse up 2 generations)
        
        Args:
            parent1: First parent creature
            parent2: Second parent creature
            
        Returns:
            Coefficient of relationship (0.0 to 1.0)
        """
        # Check if siblings (share both parents)
        if (parent1.parent1_id == parent2.parent1_id and 
            parent1.parent2_id == parent2.parent2_id and
            parent1.parent1_id is not None):
            return 0.5
        
        # Check if parent-offspring relationship
        if (parent1.creature_id == parent2.parent1_id or 
            parent1.creature_id == parent2.parent2_id or
            parent2.creature_id == parent1.parent1_id or
            parent2.creature_id == parent1.parent2_id):
            return 0.5
        
        # Check if half-siblings (share one parent)
        if (parent1.parent1_id == parent2.parent1_id and parent1.parent1_id is not None) or \
           (parent1.parent1_id == parent2.parent2_id and parent1.parent1_id is not None) or \
           (parent1.parent2_id == parent2.parent1_id and parent1.parent2_id is not None) or \
           (parent1.parent2_id == parent2.parent2_id and parent1.parent2_id is not None):
            return 0.25
        
        # Check if first cousins (simplified: check if grandparents match)
        # This is a simplified check - full implementation would traverse pedigree
        if (parent1.parent1_id is not None and parent2.parent1_id is not None):
            # Would need to load parent objects to check their parents
            # For Phase 1, we'll use a simplified approach
            pass
        
        # Default: unrelated
        return 0.0
    
    @staticmethod
    def calculate_inbreeding_coefficient(
        parent1: 'Creature',
        parent2: 'Creature'
    ) -> float:
        """
        Calculate inbreeding coefficient for offspring using Wright's formula.
        
        F_offspring = (1/2) × (1 + F_parent1) × (1 + F_parent2) × r_parents
        
        Args:
            parent1: First parent creature
            parent2: Second parent creature
            
        Returns:
            Inbreeding coefficient (0.0 to 1.0)
        """
        r_parents = Creature.calculate_relationship_coefficient(parent1, parent2)
        f_parent1 = parent1.inbreeding_coefficient
        f_parent2 = parent2.inbreeding_coefficient
        
        f_offspring = 0.5 * (1 + f_parent1) * (1 + f_parent2) * r_parents
        
        # Clamp to valid range
        return max(0.0, min(1.0, f_offspring))
    
    @classmethod
    def create_offspring(
        cls,
        parent1: 'Creature',
        parent2: 'Creature',
        birth_generation: int,
        simulation_id: int,
        traits: List['Trait'],
        rng: np.random.Generator,
        max_litters: int
    ) -> 'Creature':
        """
        Create an offspring from two parents.
        
        Args:
            parent1: First parent
            parent2: Second parent
            birth_generation: Generation when offspring is born
            simulation_id: Simulation ID
            traits: List of all traits in simulation
            rng: Random number generator
            max_litters: Maximum litters for females
            
        Returns:
            New Creature instance
        """
        # Determine sex (50/50 for now, could be configurable)
        sex = rng.choice(['male', 'female'])
        
        # Create genome by combining gametes
        max_trait_id = max(t.trait_id for t in traits) if traits else 0
        genome: List[Optional[str]] = [None] * (max_trait_id + 1)
        
        for trait in traits:
            # Get gametes from both parents
            gamete1 = parent1.produce_gamete(trait.trait_id, trait, rng)
            gamete2 = parent2.produce_gamete(trait.trait_id, trait, rng)
            
            # Combine gametes to form genotype
            if trait.trait_type.value == 'SEX_LINKED':
                if sex == 'male':
                    # Male gets single allele (from mother's X chromosome)
                    genotype = gamete1 if parent1.sex == 'female' else gamete2
                else:
                    # Female gets two alleles
                    if len(gamete1) == 1 and len(gamete2) == 1:
                        # Sort alleles for consistency (e.g., "Nc" not "cN")
                        alleles = sorted([gamete1, gamete2])
                        genotype = ''.join(alleles)
                    else:
                        # Handle multi-character alleles
                        genotype = f"{gamete1}{gamete2}"
            else:
                # Non-sex-linked: combine gametes
                if '_' in gamete1 or '_' in gamete2:
                    # Polygenic: combine gene pairs
                    pairs1 = gamete1.split('_') if '_' in gamete1 else [gamete1]
                    pairs2 = gamete2.split('_') if '_' in gamete2 else [gamete2]
                    combined = []
                    for p1, p2 in zip(pairs1, pairs2):
                        # Sort alleles within each pair for consistency
                        combined.append(''.join(sorted([p1, p2])))
                    genotype = '_'.join(combined)
                else:
                    # Simple: combine and sort for consistency
                    genotype = ''.join(sorted([gamete1, gamete2]))
            
            genome[trait.trait_id] = genotype
        
        # Calculate inbreeding coefficient
        inbreeding_coefficient = cls.calculate_inbreeding_coefficient(parent1, parent2)
        
        # Initialize litters_remaining (only for females)
        litters_remaining = max_litters if sex == 'female' else 0
        
        # All creatures are persisted immediately, so parents must have IDs
        if parent1.creature_id is None:
            raise ValueError(
                f"Parent1 (birth_gen={parent1.birth_generation}) does not have creature_id. "
                f"All creatures must be persisted immediately upon creation."
            )
        if parent2.creature_id is None:
            raise ValueError(
                f"Parent2 (birth_gen={parent2.birth_generation}) does not have creature_id. "
                f"All creatures must be persisted immediately upon creation."
            )
        parent1_id = parent1.creature_id
        parent2_id = parent2.creature_id
        
        return cls(
            simulation_id=simulation_id,
            birth_generation=birth_generation,
            sex=sex,
            genome=genome,
            parent1_id=parent1_id,
            parent2_id=parent2_id,
            inbreeding_coefficient=inbreeding_coefficient,
            litters_remaining=litters_remaining,
            lifespan=0,  # Will be set when added to population
            is_alive=True
        )

