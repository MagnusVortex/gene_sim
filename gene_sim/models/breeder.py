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
    
    def __init__(
        self,
        undesirable_phenotypes: Optional[List[dict]] = None,
        undesirable_genotypes: Optional[List[dict]] = None,
        avoid_undesirable_phenotypes: bool = False,
        avoid_undesirable_genotypes: bool = False
    ):
        """
        Initialize breeder.
        
        Args:
            undesirable_phenotypes: List of {trait_id, phenotype} dicts to avoid
            undesirable_genotypes: List of {trait_id, genotype} dicts to avoid
            avoid_undesirable_phenotypes: If True, filter out creatures with undesirable phenotypes
            avoid_undesirable_genotypes: If True, filter out creatures with undesirable genotypes
        """
        self.breeder_id: Optional[int] = None
        self.undesirable_phenotypes = undesirable_phenotypes or []
        self.undesirable_genotypes = undesirable_genotypes or []
        self.avoid_undesirable_phenotypes = avoid_undesirable_phenotypes
        self.avoid_undesirable_genotypes = avoid_undesirable_genotypes
    
    def _has_undesirable_phenotype(self, creature: 'Creature', traits: List) -> bool:
        """Check if creature has any undesirable phenotype."""
        if not self.avoid_undesirable_phenotypes or not self.undesirable_phenotypes:
            return False
        
        from .trait import Trait
        
        for undesirable in self.undesirable_phenotypes:
            trait_id = undesirable['trait_id']
            undesirable_phenotype = undesirable['phenotype']
            
            if trait_id >= len(creature.genome) or creature.genome[trait_id] is None:
                continue
            
            # Find trait to get phenotype mapping
            trait = next((t for t in traits if t.trait_id == trait_id), None)
            if trait is None:
                continue
            
            actual_phenotype = trait.get_phenotype(creature.genome[trait_id], creature.sex)
            if actual_phenotype == undesirable_phenotype:
                return True
        
        return False
    
    def _has_undesirable_genotype(self, creature: 'Creature') -> bool:
        """Check if creature has any undesirable genotype."""
        if not self.avoid_undesirable_genotypes or not self.undesirable_genotypes:
            return False
        
        for undesirable in self.undesirable_genotypes:
            trait_id = undesirable['trait_id']
            undesirable_genotype = undesirable['genotype']
            
            if trait_id >= len(creature.genome) or creature.genome[trait_id] is None:
                continue
            
            if creature.genome[trait_id] == undesirable_genotype:
                return True
        
        return False
    
    def _filter_undesirable(self, creatures: List['Creature'], traits: List) -> List['Creature']:
        """Filter out creatures with undesirable phenotypes or genotypes."""
        filtered = []
        for creature in creatures:
            if self._has_undesirable_phenotype(creature, traits):
                continue
            if self._has_undesirable_genotype(creature):
                continue
            filtered.append(creature)
        return filtered
    
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
        rng: np.random.Generator,
        traits: List = None
    ) -> List[Tuple['Creature', 'Creature']]:
        """Randomly select pairs."""
        if not eligible_males or not eligible_females:
            return []
        
        # Filter out undesirable creatures if avoidance is enabled
        if traits is None:
            traits = []
        filtered_males = self._filter_undesirable(eligible_males, traits)
        filtered_females = self._filter_undesirable(eligible_females, traits)
        
        # If filtering removed all candidates, fall back to original lists
        if not filtered_males:
            filtered_males = eligible_males
        if not filtered_females:
            filtered_females = eligible_females
        
        pairs = []
        for _ in range(num_pairs):
            male = rng.choice(filtered_males)
            female = rng.choice(filtered_females)
            pairs.append((male, female))
        
        return pairs


class InbreedingAvoidanceBreeder(Breeder):
    """Avoids pairs that would produce offspring with high inbreeding coefficient."""
    
    def __init__(
        self,
        max_inbreeding_coefficient: float = 0.25,
        undesirable_phenotypes: Optional[List[dict]] = None,
        undesirable_genotypes: Optional[List[dict]] = None,
        avoid_undesirable_phenotypes: bool = False,
        avoid_undesirable_genotypes: bool = False
    ):
        """
        Initialize inbreeding avoidance breeder.
        
        Args:
            max_inbreeding_coefficient: Maximum allowed inbreeding coefficient for offspring
            undesirable_phenotypes: List of {trait_id, phenotype} dicts to avoid
            undesirable_genotypes: List of {trait_id, genotype} dicts to avoid
            avoid_undesirable_phenotypes: If True, filter out creatures with undesirable phenotypes
            avoid_undesirable_genotypes: If True, filter out creatures with undesirable genotypes
        """
        super().__init__(undesirable_phenotypes, undesirable_genotypes, avoid_undesirable_phenotypes, avoid_undesirable_genotypes)
        self.max_inbreeding_coefficient = max_inbreeding_coefficient
    
    def select_pairs(
        self,
        eligible_males: List['Creature'],
        eligible_females: List['Creature'],
        num_pairs: int,
        rng: np.random.Generator,
        traits: List = None
    ) -> List[Tuple['Creature', 'Creature']]:
        """Select pairs that avoid high inbreeding."""
        if not eligible_males or not eligible_females:
            return []
        
        # Filter out undesirable creatures if avoidance is enabled
        if traits is None:
            traits = []
        filtered_males = self._filter_undesirable(eligible_males, traits)
        filtered_females = self._filter_undesirable(eligible_females, traits)
        
        # If filtering removed all candidates, fall back to original lists
        if not filtered_males:
            filtered_males = eligible_males
        if not filtered_females:
            filtered_females = eligible_females
        
        pairs = []
        attempts = 0
        max_attempts = num_pairs * 100  # Prevent infinite loops
        
        while len(pairs) < num_pairs and attempts < max_attempts:
            male = rng.choice(filtered_males)
            female = rng.choice(filtered_females)
            
            # Calculate potential offspring inbreeding coefficient
            potential_f = Creature.calculate_inbreeding_coefficient(male, female)
            
            if potential_f <= self.max_inbreeding_coefficient:
                pairs.append((male, female))
            
            attempts += 1
        
        # If we couldn't find enough pairs, fill with random pairs
        while len(pairs) < num_pairs:
            male = rng.choice(filtered_males)
            female = rng.choice(filtered_females)
            pairs.append((male, female))
        
        return pairs


class KennelClubBreeder(Breeder):
    """Selects pairs based on target phenotypes with kennel club guidelines."""
    
    def __init__(
        self,
        target_phenotypes: List[dict],
        max_inbreeding_coefficient: Optional[float] = None,
        required_phenotype_ranges: Optional[List[dict]] = None,
        undesirable_phenotypes: Optional[List[dict]] = None,
        undesirable_genotypes: Optional[List[dict]] = None,
        avoid_undesirable_phenotypes: bool = False,
        avoid_undesirable_genotypes: bool = False
    ):
        """
        Initialize kennel club breeder.
        
        Args:
            target_phenotypes: List of {trait_id, phenotype} dicts
            max_inbreeding_coefficient: Maximum allowed inbreeding (optional)
            required_phenotype_ranges: List of {trait_id, min, max} dicts (optional)
            undesirable_phenotypes: List of {trait_id, phenotype} dicts to avoid
            undesirable_genotypes: List of {trait_id, genotype} dicts to avoid
            avoid_undesirable_phenotypes: If True, filter out creatures with undesirable phenotypes
            avoid_undesirable_genotypes: If True, filter out creatures with undesirable genotypes
        """
        super().__init__(undesirable_phenotypes, undesirable_genotypes, avoid_undesirable_phenotypes, avoid_undesirable_genotypes)
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
        
        # Kennel club breeder always filters out undesirable genotypes
        # Also respects global avoidance flags for phenotypes
        filtered_males = eligible_males.copy()
        filtered_females = eligible_females.copy()
        
        # Always filter undesirable genotypes (kennel club requirement)
        # Note: We bypass the avoid_undesirable_genotypes flag check for kennel club
        if self.undesirable_genotypes:
            for undesirable in self.undesirable_genotypes:
                trait_id = undesirable['trait_id']
                undesirable_genotype = undesirable['genotype']
                filtered_males = [m for m in filtered_males 
                                if trait_id >= len(m.genome) or m.genome[trait_id] is None or m.genome[trait_id] != undesirable_genotype]
                filtered_females = [f for f in filtered_females 
                                  if trait_id >= len(f.genome) or f.genome[trait_id] is None or f.genome[trait_id] != undesirable_genotype]
        
        # Filter undesirable phenotypes if global flag is enabled
        if self.avoid_undesirable_phenotypes:
            filtered_males = [m for m in filtered_males if not self._has_undesirable_phenotype(m, traits)]
            filtered_females = [f for f in filtered_females if not self._has_undesirable_phenotype(f, traits)]
        
        # If filtering removed all candidates, fall back to original lists
        if not filtered_males:
            filtered_males = eligible_males
        if not filtered_females:
            filtered_females = eligible_females
        
        # Filter creatures that match target phenotypes
        matching_males = [m for m in filtered_males if self._matches_target_phenotypes(m, traits)]
        matching_females = [f for f in filtered_females if self._matches_target_phenotypes(f, traits)]
        
        # If no matches, fall back to filtered lists (which may be original if no filtering)
        if not matching_males:
            matching_males = filtered_males
        if not matching_females:
            matching_females = filtered_females
        
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
            male = rng.choice(filtered_males)
            female = rng.choice(filtered_females)
            pairs.append((male, female))
        
        return pairs


class MillBreeder(Breeder):
    """Selects pairs based on target phenotypes. Mill breeders always avoid undesirable phenotypes."""
    
    def __init__(
        self,
        target_phenotypes: List[dict],
        undesirable_phenotypes: Optional[List[dict]] = None,
        undesirable_genotypes: Optional[List[dict]] = None,
        avoid_undesirable_phenotypes: bool = False,
        avoid_undesirable_genotypes: bool = False
    ):
        """
        Initialize mill breeder.
        
        Args:
            target_phenotypes: List of {trait_id, phenotype} dicts
            undesirable_phenotypes: List of {trait_id, phenotype} dicts to avoid
            undesirable_genotypes: List of {trait_id, genotype} dicts to avoid
            avoid_undesirable_phenotypes: Ignored - mill breeders always avoid undesirable phenotypes
            avoid_undesirable_genotypes: If True, filter out creatures with undesirable genotypes
        """
        super().__init__(undesirable_phenotypes, undesirable_genotypes, avoid_undesirable_phenotypes, avoid_undesirable_genotypes)
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
        """Select pairs based on target phenotypes. Mill breeders always avoid undesirable phenotypes."""
        if not eligible_males or not eligible_females:
            return []
        
        if traits is None:
            traits = []
        
        # Mill breeder always filters out undesirable phenotypes
        # Also respects global avoidance flag for genotypes
        filtered_males = eligible_males.copy()
        filtered_females = eligible_females.copy()
        
        # Always filter undesirable phenotypes (mill requirement)
        # Note: We bypass the avoid_undesirable_phenotypes flag check for mill
        if self.undesirable_phenotypes:
            from .trait import Trait
            for undesirable in self.undesirable_phenotypes:
                trait_id = undesirable['trait_id']
                undesirable_phenotype = undesirable['phenotype']
                trait = next((t for t in traits if t.trait_id == trait_id), None)
                if trait is not None:
                    filtered_males = [m for m in filtered_males 
                                    if trait_id >= len(m.genome) or m.genome[trait_id] is None or 
                                    trait.get_phenotype(m.genome[trait_id], m.sex) != undesirable_phenotype]
                    filtered_females = [f for f in filtered_females 
                                      if trait_id >= len(f.genome) or f.genome[trait_id] is None or 
                                      trait.get_phenotype(f.genome[trait_id], f.sex) != undesirable_phenotype]
        
        # Filter undesirable genotypes if global flag is enabled
        if self.avoid_undesirable_genotypes:
            filtered_males = [m for m in filtered_males if not self._has_undesirable_genotype(m)]
            filtered_females = [f for f in filtered_females if not self._has_undesirable_genotype(f)]
        
        # If filtering removed all candidates, fall back to original lists
        if not filtered_males:
            filtered_males = eligible_males
        if not filtered_females:
            filtered_females = eligible_females
        
        # Filter creatures that match target phenotypes
        matching_males = [m for m in filtered_males if self._matches_target_phenotypes(m, traits)]
        matching_females = [f for f in filtered_females if self._matches_target_phenotypes(f, traits)]
        
        # If no matches, fall back to filtered lists (which may be original if no filtering)
        if not matching_males:
            matching_males = filtered_males
        if not matching_females:
            matching_females = filtered_females
        
        pairs = []
        for _ in range(num_pairs):
            male = rng.choice(matching_males)
            female = rng.choice(matching_females)
            pairs.append((male, female))
        
        return pairs

