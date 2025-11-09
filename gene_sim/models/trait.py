"""Trait and Genotype models for gene_sim."""

from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass


class TraitType(Enum):
    """Trait inheritance pattern types."""
    SIMPLE_MENDELIAN = "SIMPLE_MENDELIAN"
    INCOMPLETE_DOMINANCE = "INCOMPLETE_DOMINANCE"
    CODOMINANCE = "CODOMINANCE"
    SEX_LINKED = "SEX_LINKED"
    POLYGENIC = "POLYGENIC"


@dataclass
class Genotype:
    """Represents a genotype with its phenotype mapping."""
    genotype: str  # e.g., "BB", "Bb", "bb", "H1H1_H2H2_H3H3"
    phenotype: str  # e.g., "Black", "Brown", "80.0"
    initial_freq: float  # Normalized frequency (0.0 to 1.0)
    sex: Optional[str] = None  # For sex-linked traits: 'male' or 'female'
    
    def __post_init__(self):
        """Validate genotype data."""
        if not (0.0 <= self.initial_freq <= 1.0):
            raise ValueError(f"initial_freq must be between 0.0 and 1.0, got {self.initial_freq}")
        if self.sex is not None and self.sex not in ['male', 'female']:
            raise ValueError(f"sex must be 'male' or 'female', got {self.sex}")


@dataclass
class Trait:
    """Represents a genetic trait with its possible genotypes."""
    trait_id: int  # 0-99
    name: str
    trait_type: TraitType
    genotypes: List[Genotype]
    
    def __post_init__(self):
        """Validate trait data."""
        if not (0 <= self.trait_id < 100):
            raise ValueError(f"trait_id must be between 0 and 99, got {self.trait_id}")
        if not self.genotypes:
            raise ValueError(f"Trait {self.trait_id} must have at least one genotype")
        
        # Validate genotype frequencies sum to 1.0 (with small tolerance)
        total_freq = sum(g.initial_freq for g in self.genotypes)
        if abs(total_freq - 1.0) > 0.001:
            raise ValueError(f"Trait {self.trait_id} genotype frequencies sum to {total_freq}, expected 1.0")
        
        # Validate sex-linked traits have sex specified
        if self.trait_type == TraitType.SEX_LINKED:
            for genotype in self.genotypes:
                if genotype.sex is None:
                    raise ValueError(f"Trait {self.trait_id} (SEX_LINKED) genotype {genotype.genotype} must specify sex")
    
    def get_phenotype(self, genotype_str: str, sex: Optional[str] = None) -> Optional[str]:
        """
        Get phenotype for a given genotype string.
        
        Args:
            genotype_str: Genotype string to look up
            sex: Optional sex for sex-linked traits
            
        Returns:
            Phenotype string, or None if not found
        """
        for genotype in self.genotypes:
            if genotype.genotype == genotype_str:
                # For sex-linked traits, sex must match
                if self.trait_type == TraitType.SEX_LINKED:
                    if genotype.sex == sex:
                        return genotype.phenotype
                else:
                    return genotype.phenotype
        return None
    
    def get_genotype_by_frequency(self, rng) -> Genotype:
        """
        Sample a genotype based on initial frequencies.
        
        Args:
            rng: NumPy random number generator
            
        Returns:
            Randomly sampled Genotype based on frequencies
        """
        probs = [g.initial_freq for g in self.genotypes]
        idx = rng.choice(len(self.genotypes), p=probs)
        return self.genotypes[idx]
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'Trait':
        """
        Create Trait from configuration dictionary.
        
        Args:
            config: Trait configuration dictionary
            
        Returns:
            Trait instance
        """
        trait_type_str = config['trait_type']
        try:
            trait_type = TraitType(trait_type_str)
        except ValueError:
            raise ValueError(f"Invalid trait_type: {trait_type_str}")
        
        genotypes = [
            Genotype(
                genotype=g['genotype'],
                phenotype=g['phenotype'],
                initial_freq=g['initial_freq'],
                sex=g.get('sex')
            )
            for g in config['genotypes']
        ]
        
        return cls(
            trait_id=config['trait_id'],
            name=config['name'],
            trait_type=trait_type,
            genotypes=genotypes
        )

