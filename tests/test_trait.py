"""Tests for Trait model."""

import pytest
import numpy as np
from gene_sim.models.trait import Trait, Genotype, TraitType


def test_genotype_validation():
    """Test Genotype validation."""
    # Valid genotype
    g = Genotype("BB", "Black", 0.5)
    assert g.genotype == "BB"
    assert g.phenotype == "Black"
    assert g.initial_freq == 0.5
    
    # Invalid frequency
    with pytest.raises(ValueError):
        Genotype("BB", "Black", 1.5)
    
    # Invalid sex
    with pytest.raises(ValueError):
        Genotype("NN", "Normal", 0.5, sex="invalid")


def test_trait_validation():
    """Test Trait validation."""
    genotypes = [
        Genotype("BB", "Black", 0.36),
        Genotype("Bb", "Black", 0.48),
        Genotype("bb", "Brown", 0.16),
    ]
    
    trait = Trait(0, "Coat Color", TraitType.SIMPLE_MENDELIAN, genotypes)
    assert trait.trait_id == 0
    assert trait.name == "Coat Color"
    assert len(trait.genotypes) == 3
    
    # Invalid trait_id
    with pytest.raises(ValueError):
        Trait(100, "Test", TraitType.SIMPLE_MENDELIAN, genotypes)
    
    # Frequencies don't sum to 1.0
    bad_genotypes = [
        Genotype("BB", "Black", 0.5),
        Genotype("bb", "Brown", 0.3),
    ]
    with pytest.raises(ValueError):
        Trait(0, "Test", TraitType.SIMPLE_MENDELIAN, bad_genotypes)
    
    # Sex-linked trait missing sex
    sex_linked_genotypes = [
        Genotype("NN", "Normal", 0.5, sex=None),  # Missing sex
    ]
    with pytest.raises(ValueError):
        Trait(0, "Test", TraitType.SEX_LINKED, sex_linked_genotypes)


def test_trait_get_phenotype():
    """Test getting phenotype from genotype."""
    genotypes = [
        Genotype("BB", "Black", 0.36),
        Genotype("Bb", "Black", 0.48),
        Genotype("bb", "Brown", 0.16),
    ]
    trait = Trait(0, "Coat Color", TraitType.SIMPLE_MENDELIAN, genotypes)
    
    assert trait.get_phenotype("BB") == "Black"
    assert trait.get_phenotype("Bb") == "Black"
    assert trait.get_phenotype("bb") == "Brown"
    assert trait.get_phenotype("XX") is None


def test_trait_get_genotype_by_frequency():
    """Test sampling genotype by frequency."""
    genotypes = [
        Genotype("BB", "Black", 0.5),
        Genotype("bb", "Brown", 0.5),
    ]
    trait = Trait(0, "Test", TraitType.SIMPLE_MENDELIAN, genotypes)
    
    rng = np.random.Generator(np.random.PCG64(42))
    sampled = trait.get_genotype_by_frequency(rng)
    assert sampled in trait.genotypes


def test_trait_from_config():
    """Test creating Trait from config."""
    config = {
        'trait_id': 0,
        'name': 'Coat Color',
        'trait_type': 'SIMPLE_MENDELIAN',
        'genotypes': [
            {'genotype': 'BB', 'phenotype': 'Black', 'initial_freq': 0.36},
            {'genotype': 'Bb', 'phenotype': 'Black', 'initial_freq': 0.48},
            {'genotype': 'bb', 'phenotype': 'Brown', 'initial_freq': 0.16},
        ]
    }
    
    trait = Trait.from_config(config)
    assert trait.trait_id == 0
    assert trait.name == "Coat Color"
    assert trait.trait_type == TraitType.SIMPLE_MENDELIAN
    assert len(trait.genotypes) == 3

