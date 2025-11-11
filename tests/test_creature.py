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
        birth_cycle=0,
        sex="male",
        genome=genome,
        parent1_id=None,
        parent2_id=None,
        inbreeding_coefficient=0.0,
        lifespan=10,
        is_alive=True,
    )


def test_creature_creation(founder_creature):
    """Test creature creation."""
    assert founder_creature.birth_cycle == 0
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
        birth_cycle=0,
        sex="male",
        genome=genome,
        parent1_id=None,
        parent2_id=None
    )
    
    # Invalid: founder with parent
    with pytest.raises(ValueError):
        Creature(
            simulation_id=1,
            birth_cycle=0,
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
    # Create a mock config for testing
    from gene_sim.config import CreatureArchetypeConfig, SimulationConfig
    archetype = CreatureArchetypeConfig(
        remove_ineligible_immediately=False,
        sexual_maturity_months=12.0,
        max_fertility_age_years={'male': 10.0, 'female': 8.0},
        gestation_period_days=90.0,
        nursing_period_days=60.0,
        menstrual_cycle_days=28.0,
        nearing_end_cycles=3,
        litter_size_min=3,
        litter_size_max=6,
        gestation_cycles=3,
        nursing_cycles=2,
        maturity_cycles=13,
        max_fertility_age_cycles={'male': 130, 'female': 104},
        lifespan_cycles_min=156,
        lifespan_cycles_max=195
    )
    config = SimulationConfig(
        seed=42,
        years=0.5,
        cycles=13,  # Calculated from years (0.5 * 365.25 / 28 ≈ 13)
        initial_population_size=100,
        initial_sex_ratio={'male': 0.5, 'female': 0.5},
        creature_archetype=archetype,
        target_phenotypes=[],
        undesirable_phenotypes=[],
        undesirable_genotypes=[],
        breeders=None,
        traits=[],
        raw_config={}
    )
    
    genome1 = [None] * 1
    genome1[0] = "BB"
    parent1 = Creature(
        simulation_id=1,
        birth_cycle=0,
        sex="male",
        genome=genome1,
        creature_id=1,
    )
    
    genome2 = [None] * 1
    genome2[0] = "bb"
    parent2 = Creature(
        simulation_id=1,
        birth_cycle=0,
        sex="female",
        genome=genome2,
        creature_id=2
    )
    
    rng = np.random.Generator(np.random.PCG64(42))
    offspring = Creature.create_offspring(
        parent1, parent2, conception_cycle=1, simulation_id=1, 
        traits=sample_traits, rng=rng, config=config
    )
    
    assert offspring.birth_cycle > 1  # Birth happens after gestation
    assert offspring.conception_cycle == 1
    assert offspring.parent1_id == 1
    assert offspring.parent2_id == 2
    assert offspring.genome[0] in ["Bb", "bB", "BB", "bb"]


def test_creature_relationship_coefficient():
    """Test relationship coefficient calculation."""
    genome = [None] * 1
    genome[0] = "BB"
    
    # Siblings
    parent1 = Creature(1, birth_cycle=0, sex="male", genome=genome, creature_id=1)
    parent2 = Creature(1, birth_cycle=0, sex="female", genome=genome, creature_id=2)
    
    child1 = Creature(1, birth_cycle=1, sex="male", genome=genome, parent1_id=1, parent2_id=2, creature_id=3)
    child2 = Creature(1, birth_cycle=1, sex="female", genome=genome, parent1_id=1, parent2_id=2, creature_id=4)
    
    r = Creature.calculate_relationship_coefficient(child1, child2)
    assert r == 0.5  # Full siblings


def test_creature_inbreeding_coefficient():
    """Test inbreeding coefficient calculation."""
    genome = [None] * 1
    genome[0] = "BB"
    
    # Unrelated parents
    parent1 = Creature(1, birth_cycle=0, sex="male", genome=genome, inbreeding_coefficient=0.0, creature_id=1)
    parent2 = Creature(1, birth_cycle=0, sex="female", genome=genome, inbreeding_coefficient=0.0, creature_id=2)
    
    f = Creature.calculate_inbreeding_coefficient(parent1, parent2)
    assert f == 0.0  # Unrelated parents


def test_litter_size_produces_multiple_offspring(sample_traits):
    """Test that a single breeding pair produces multiple offspring according to litter_size configuration."""
    from gene_sim.config import CreatureArchetypeConfig, SimulationConfig
    
    # Create config with specific litter size
    archetype = CreatureArchetypeConfig(
        remove_ineligible_immediately=False,
        sexual_maturity_months=6.0,
        max_fertility_age_years={'male': 10.0, 'female': 8.0},
        gestation_period_days=60.0,
        nursing_period_days=30.0,
        menstrual_cycle_days=28.0,
        nearing_end_cycles=3,
        litter_size_min=3,
        litter_size_max=6,
        gestation_cycles=2,
        nursing_cycles=1,
        maturity_cycles=1,
        max_fertility_age_cycles={'male': 130, 'female': 104},
        lifespan_cycles_min=156,
        lifespan_cycles_max=195
    )
    config = SimulationConfig(
        seed=42,
        years=0.5,
        cycles=13,
        initial_population_size=2,
        initial_sex_ratio={'male': 0.5, 'female': 0.5},
        creature_archetype=archetype,
        target_phenotypes=[],
        undesirable_phenotypes=[],
        undesirable_genotypes=[],
        breeders=None,
        traits=sample_traits,
        raw_config={}
    )
    
    # Create a single breeding pair
    genome1 = [None] * 1
    genome1[0] = "BB"
    parent1 = Creature(
        simulation_id=1,
        birth_cycle=0,
        sex="male",
        genome=genome1,
        parent1_id=None,
        parent2_id=None,
        creature_id=1,
        sexual_maturity_cycle=0,
        max_fertility_age_cycle=100,
        lifespan=200,
        is_alive=True
    )
    
    genome2 = [None] * 1
    genome2[0] = "bb"
    parent2 = Creature(
        simulation_id=1,
        birth_cycle=0,
        sex="female",
        genome=genome2,
        parent1_id=None,
        parent2_id=None,
        creature_id=2,
        sexual_maturity_cycle=0,
        max_fertility_age_cycle=100,
        lifespan=200,
        is_alive=True
    )
    
    # Simulate the breeding process as it happens in generation.py
    # This tests that litter_size is used correctly
    rng = np.random.Generator(np.random.PCG64(42))
    offspring = []
    
    # Determine litter size (as done in generation.py)
    litter_size = rng.integers(
        archetype.litter_size_min,
        archetype.litter_size_max + 1  # +1 because randint is exclusive on upper bound
    )
    
    # Create multiple offspring (as done in generation.py)
    for _ in range(litter_size):
        child = Creature.create_offspring(
            parent1=parent1,
            parent2=parent2,
            conception_cycle=0,
            simulation_id=1,
            traits=sample_traits,
            rng=rng,
            config=config
        )
        child.parent1_id = parent1.creature_id
        child.parent2_id = parent2.creature_id
        offspring.append(child)
    
    # Verify litter size is within configured range
    assert len(offspring) >= archetype.litter_size_min, \
        f"Expected at least {archetype.litter_size_min} offspring, got {len(offspring)}"
    assert len(offspring) <= archetype.litter_size_max, \
        f"Expected at most {archetype.litter_size_max} offspring, got {len(offspring)}"
    
    # Verify all offspring share the same parents
    for child in offspring:
        assert child.parent1_id == parent1.creature_id, \
            f"Offspring should have parent1_id={parent1.creature_id}, got {child.parent1_id}"
        assert child.parent2_id == parent2.creature_id, \
            f"Offspring should have parent2_id={parent2.creature_id}, got {child.parent2_id}"
        assert child.conception_cycle == 0, \
            f"All offspring should have conception_cycle=0, got {child.conception_cycle}"
    
    # Verify we got multiple offspring (not just 1)
    assert len(offspring) > 1, \
        f"Expected multiple offspring from single breeding pair, got {len(offspring)}"
    
    # Verify offspring have valid genomes
    for child in offspring:
        assert child.genome[0] is not None, \
            f"Offspring should have a valid genotype, got {child.genome[0]}"
        # With BB x bb parents, offspring should be Bb (heterozygous)
        assert child.genome[0] in ["Bb", "bB"], \
            f"Expected heterozygous genotype (Bb) from BB x bb parents, got {child.genome[0]}"

