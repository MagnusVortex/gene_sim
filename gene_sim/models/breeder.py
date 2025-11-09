"""Breeder models for selecting mating pairs."""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from .creature import Creature
    from ..config import SimulationConfig
else:
    from .creature import Creature


class Breeder(ABC):
    """Abstract base class for breeder strategies."""
    
    @abstractmethod
    def select_pairs(
        self,
        eligible_males: List['Creature'],
        eligible_females: List['Creature'],
        num_pairs: int,
        rng: np.random.Generator
    ) -> List[Tuple['Creature', 'Creature']]:
        """
        Select mating pairs from eligible creatures.
        
        Args:
            eligible_males: Pre-filtered list of eligible male creatures
            eligible_females: Pre-filtered list of eligible female creatures
            num_pairs: Number of pairs to select
            rng: Seeded random number generator
            
        Returns:
            List of (male, female) tuples for reproduction
        """
        pass


class RandomBreeder(Breeder):
    """Randomly pairs eligible males and females with no selection bias."""
    
    def select_pairs(
        self,
        eligible_males: List['Creature'],
        eligible_females: List['Creature'],
        num_pairs: int,
        rng: np.random.Generator
    ) -> List[Tuple['Creature', 'Creature']]:
        """Randomly select pairs."""
        if not eligible_males or not eligible_females:
            return []
        
        pairs = []
        for _ in range(num_pairs):
            male = rng.choice(eligible_males)
            female = rng.choice(eligible_females)
            pairs.append((male, female))
        
        return pairs


class InbreedingAvoidanceBreeder(Breeder):
    """Avoids pairs that would produce offspring with high inbreeding coefficient."""
    
    def __init__(self, max_inbreeding_coefficient: float = 0.25):
        """
        Initialize inbreeding avoidance breeder.
        
        Args:
            max_inbreeding_coefficient: Maximum allowed inbreeding coefficient for offspring
        """
        self.max_inbreeding_coefficient = max_inbreeding_coefficient
    
    def select_pairs(
        self,
        eligible_males: List['Creature'],
        eligible_females: List['Creature'],
        num_pairs: int,
        rng: np.random.Generator
    ) -> List[Tuple['Creature', 'Creature']]:
        """Select pairs that avoid high inbreeding."""
        if not eligible_males or not eligible_females:
            return []
        
        pairs = []
        attempts = 0
        max_attempts = num_pairs * 100  # Prevent infinite loops
        
        while len(pairs) < num_pairs and attempts < max_attempts:
            male = rng.choice(eligible_males)
            female = rng.choice(eligible_females)
            
            # Calculate potential offspring inbreeding coefficient
            potential_f = Creature.calculate_inbreeding_coefficient(male, female)
            
            if potential_f <= self.max_inbreeding_coefficient:
                pairs.append((male, female))
            
            attempts += 1
        
        # If we couldn't find enough pairs, fill with random pairs
        while len(pairs) < num_pairs:
            male = rng.choice(eligible_males)
            female = rng.choice(eligible_females)
            pairs.append((male, female))
        
        return pairs


class KennelClubBreeder(Breeder):
    """Selects pairs based on target phenotypes with kennel club guidelines."""
    
    def __init__(
        self,
        target_phenotypes: List[dict],
        max_inbreeding_coefficient: Optional[float] = None,
        required_phenotype_ranges: Optional[List[dict]] = None
    ):
        """
        Initialize kennel club breeder.
        
        Args:
            target_phenotypes: List of {trait_id, phenotype} dicts
            max_inbreeding_coefficient: Maximum allowed inbreeding (optional)
            required_phenotype_ranges: List of {trait_id, min, max} dicts (optional)
        """
        self.target_phenotypes = target_phenotypes
        self.max_inbreeding_coefficient = max_inbreeding_coefficient
        self.required_phenotype_ranges = required_phenotype_ranges or []
    
    def _matches_target_phenotypes(self, creature: 'Creature', traits: List) -> bool:
        """Check if creature matches target phenotypes."""
        from .trait import Trait
        
        for target in self.target_phenotypes:
            trait_id = target['trait_id']
            target_phenotype = target['phenotype']
            
            if trait_id >= len(creature.genome) or creature.genome[trait_id] is None:
                return False
            
            # Find trait to get phenotype mapping
            trait = next((t for t in traits if t.trait_id == trait_id), None)
            if trait is None:
                return False
            
            actual_phenotype = trait.get_phenotype(creature.genome[trait_id], creature.sex)
            if actual_phenotype != target_phenotype:
                return False
        
        return True
    
    def _matches_phenotype_ranges(self, creature: 'Creature', traits: List) -> bool:
        """Check if creature matches required phenotype ranges."""
        from .trait import Trait
        
        for range_req in self.required_phenotype_ranges:
            trait_id = range_req['trait_id']
            min_val = float(range_req['min'])
            max_val = float(range_req['max'])
            
            if trait_id >= len(creature.genome) or creature.genome[trait_id] is None:
                return False
            
            trait = next((t for t in traits if t.trait_id == trait_id), None)
            if trait is None:
                return False
            
            phenotype_str = trait.get_phenotype(creature.genome[trait_id], creature.sex)
            try:
                phenotype_val = float(phenotype_str)
                if not (min_val <= phenotype_val <= max_val):
                    return False
            except ValueError:
                # Not a numeric phenotype, skip range check
                pass
        
        return True
    
    def select_pairs(
        self,
        eligible_males: List['Creature'],
        eligible_females: List['Creature'],
        num_pairs: int,
        rng: np.random.Generator,
        traits: List = None
    ) -> List[Tuple['Creature', 'Creature']]:
        """Select pairs based on target phenotypes with guidelines."""
        if not eligible_males or not eligible_females:
            return []
        
        if traits is None:
            traits = []
        
        # Filter creatures that match target phenotypes
        matching_males = [m for m in eligible_males if self._matches_target_phenotypes(m, traits)]
        matching_females = [f for f in eligible_females if self._matches_target_phenotypes(f, traits)]
        
        # If no matches, fall back to all eligible
        if not matching_males:
            matching_males = eligible_males
        if not matching_females:
            matching_females = eligible_females
        
        pairs = []
        attempts = 0
        max_attempts = num_pairs * 100
        
        while len(pairs) < num_pairs and attempts < max_attempts:
            male = rng.choice(matching_males)
            female = rng.choice(matching_females)
            
            # Check inbreeding limit if set
            if self.max_inbreeding_coefficient is not None:
                potential_f = Creature.calculate_inbreeding_coefficient(male, female)
                if potential_f > self.max_inbreeding_coefficient:
                    attempts += 1
                    continue
            
            # Check phenotype ranges if set
            if self.required_phenotype_ranges:
                if not (self._matches_phenotype_ranges(male, traits) and 
                        self._matches_phenotype_ranges(female, traits)):
                    attempts += 1
                    continue
            
            pairs.append((male, female))
            attempts += 1
        
        # Fill remaining with random pairs if needed
        while len(pairs) < num_pairs:
            male = rng.choice(eligible_males)
            female = rng.choice(eligible_females)
            pairs.append((male, female))
        
        return pairs


class UnrestrictedPhenotypeBreeder(Breeder):
    """Selects pairs based on target phenotypes without restrictions."""
    
    def __init__(self, target_phenotypes: List[dict]):
        """
        Initialize unrestricted phenotype breeder.
        
        Args:
            target_phenotypes: List of {trait_id, phenotype} dicts
        """
        self.target_phenotypes = target_phenotypes
    
    def _matches_target_phenotypes(self, creature: 'Creature', traits: List) -> bool:
        """Check if creature matches target phenotypes."""
        from .trait import Trait
        
        for target in self.target_phenotypes:
            trait_id = target['trait_id']
            target_phenotype = target['phenotype']
            
            if trait_id >= len(creature.genome) or creature.genome[trait_id] is None:
                return False
            
            trait = next((t for t in traits if t.trait_id == trait_id), None)
            if trait is None:
                return False
            
            actual_phenotype = trait.get_phenotype(creature.genome[trait_id], creature.sex)
            if actual_phenotype != target_phenotype:
                return False
        
        return True
    
    def select_pairs(
        self,
        eligible_males: List['Creature'],
        eligible_females: List['Creature'],
        num_pairs: int,
        rng: np.random.Generator,
        traits: List = None
    ) -> List[Tuple['Creature', 'Creature']]:
        """Select pairs based solely on target phenotypes."""
        if not eligible_males or not eligible_females:
            return []
        
        if traits is None:
            traits = []
        
        # Filter creatures that match target phenotypes
        matching_males = [m for m in eligible_males if self._matches_target_phenotypes(m, traits)]
        matching_females = [f for f in eligible_females if self._matches_target_phenotypes(f, traits)]
        
        # If no matches, fall back to all eligible
        if not matching_males:
            matching_males = eligible_males
        if not matching_females:
            matching_females = eligible_females
        
        pairs = []
        for _ in range(num_pairs):
            male = rng.choice(matching_males)
            female = rng.choice(matching_females)
            pairs.append((male, female))
        
        return pairs

