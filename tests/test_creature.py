"""Tests for Creature model."""

import pytest
import numpy as np
from gene_sim.models.creature import Creature
from gene_sim.models.trait import Trait, Genotype, TraitType


@pytest.fixture
def sample_traits():
    """Create sample traits for testing."""
    return [
        Trait(0, "Coat Color", TraitType.SIMPLE_MENDELIAN, [
            Genotype("BB", "Black", 0.36),
            Genotype("Bb", "Black", 0.48),
            Genotype("bb", "Brown", 0.16),
        ])
    ]


@pytest.fixture
def founder_creature():
    """Create a founder creature."""
    genome = [None] * 1
    genome[0] = "BB"
    return Creature(
        simulation_id=1,
        birth_generation=0,
        sex="male",
        genome=genome,
        parent1_id=None,
        parent2_id=None,
        inbreeding_coefficient=0.0,
        litters_remaining=0,
        lifespan=10,
        is_alive=True
    )


def test_creature_creation(founder_creature):
    """Test creature creation."""
    assert founder_creature.birth_generation == 0
    assert founder_creature.sex == "male"
    assert founder_creature.inbreeding_coefficient == 0.0
    assert founder_creature.parent1_id is None
    assert founder_creature.parent2_id is None


def test_creature_founder_validation():
    """Test that founders must have no parents."""
    genome = [None] * 1
    genome[0] = "BB"
    
    # Valid founder
    Creature(
        simulation_id=1,
        birth_generation=0,
        sex="male",
        genome=genome,
        parent1_id=None,
        parent2_id=None
    )
    
    # Invalid: founder with parent
    with pytest.raises(ValueError):
        Creature(
            simulation_id=1,
            birth_generation=0,
            sex="male",
            genome=genome,
            parent1_id=1,
            parent2_id=None
        )


def test_creature_calculate_age(founder_creature):
    """Test age calculation."""
    assert founder_creature.calculate_age(0) == 0
    assert founder_creature.calculate_age(5) == 5
    assert founder_creature.calculate_age(10) == 10


def test_creature_produce_gamete(founder_creature, sample_traits):
    """Test gamete production."""
    trait = sample_traits[0]
    rng = np.random.Generator(np.random.PCG64(42))
    
    gamete = founder_creature.produce_gamete(0, trait, rng)
    assert gamete in ["B", "b"]


def test_creature_create_offspring(sample_traits):
    """Test creating offspring."""
    genome1 = [None] * 1
    genome1[0] = "BB"
    parent1 = Creature(
        simulation_id=1,
        birth_generation=0,
        sex="male",
        genome=genome1,
        creature_id=1
    )
    
    genome2 = [None] * 1
    genome2[0] = "bb"
    parent2 = Creature(
        simulation_id=1,
        birth_generation=0,
        sex="female",
        genome=genome2,
        creature_id=2
    )
    
    rng = np.random.Generator(np.random.PCG64(42))
    offspring = Creature.create_offspring(
        parent1, parent2, 1, 1, sample_traits, rng, max_litters=5
    )
    
    assert offspring.birth_generation == 1
    assert offspring.parent1_id == 1
    assert offspring.parent2_id == 2
    assert offspring.genome[0] in ["Bb", "bB", "BB", "bb"]


def test_creature_relationship_coefficient():
    """Test relationship coefficient calculation."""
    genome = [None] * 1
    genome[0] = "BB"
    
    # Siblings
    parent1 = Creature(1, 0, "male", genome, creature_id=1)
    parent2 = Creature(1, 0, "female", genome, creature_id=2)
    
    child1 = Creature(1, 1, "male", genome, parent1_id=1, parent2_id=2, creature_id=3)
    child2 = Creature(1, 1, "female", genome, parent1_id=1, parent2_id=2, creature_id=4)
    
    r = Creature.calculate_relationship_coefficient(child1, child2)
    assert r == 0.5  # Full siblings


def test_creature_inbreeding_coefficient():
    """Test inbreeding coefficient calculation."""
    genome = [None] * 1
    genome[0] = "BB"
    
    # Unrelated parents
    parent1 = Creature(1, 0, "male", genome, inbreeding_coefficient=0.0, creature_id=1)
    parent2 = Creature(1, 0, "female", genome, inbreeding_coefficient=0.0, creature_id=2)
    
    f = Creature.calculate_inbreeding_coefficient(parent1, parent2)
    assert f == 0.0  # Unrelated parents

