"""Tests for Population model."""

import pytest
import sqlite3
import tempfile
from gene_sim.models.population import Population
from gene_sim.models.creature import Creature
from gene_sim.models.trait import Trait, Genotype, TraitType


@pytest.fixture
def sample_config():
    """Create sample simulation config."""
    # Create a minimal config dict for testing
    class MockConfig:
        def __init__(self):
            self.creature_archetype = type('obj', (object,), {
                'remove_ineligible_immediately': False
            })()
    
    return MockConfig()


@pytest.fixture
def sample_creature():
    """Create a sample creature."""
    genome = [None] * 1
    genome[0] = "BB"
    return Creature(
        simulation_id=1,
        birth_cycle=0,
        sex="male",
        genome=genome,
        lifespan=10
    )


def test_population_add_creatures(sample_creature):
    """Test adding creatures to population."""
    population = Population()
    population.add_creatures([sample_creature], current_cycle=0)
    
    assert len(population.creatures) == 1
    assert len(population.age_out) > 0
    assert len(population.age_out[10]) == 1  # Should be in slot 10 (lifespan)


def test_population_get_eligible_males(sample_config, sample_creature):
    """Test getting eligible males."""
    population = Population()
    population.add_creatures([sample_creature], current_cycle=0)
    
    eligible = population.get_eligible_males(0, sample_config)
    assert len(eligible) == 1
    assert eligible[0] == sample_creature


def test_population_get_aged_out_creatures(sample_creature):
    """Test getting aged-out creatures."""
    population = Population()
    population.add_creatures([sample_creature], current_cycle=0)
    
    # Creature with lifespan 10 should age out at generation 10
    # So it should be in age_out[10] when added at generation 0
    # At generation 0, age_out[0] should be empty
    aged_out = population.get_aged_out_creatures()
    # At generation 0, nothing ages out yet
    assert len(aged_out) == 0
    
    # Manually set up for testing: put creature in age_out[0]
    population.age_out = [[sample_creature]]
    aged_out = population.get_aged_out_creatures()
    assert len(aged_out) == 1
    assert aged_out[0] == sample_creature


def test_population_calculate_genotype_frequencies(sample_creature):
    """Test calculating genotype frequencies."""
    population = Population()
    
    # Add creatures with different genotypes
    genome1 = [None] * 1
    genome1[0] = "BB"
    creature1 = Creature(1, 0, "male", genome1, lifespan=10)
    
    genome2 = [None] * 1
    genome2[0] = "bb"
    creature2 = Creature(1, 0, "female", genome2, lifespan=10)
    
    population.add_creatures([creature1, creature2], current_cycle=0)
    
    frequencies = population.calculate_genotype_frequencies(0)
    assert frequencies["BB"] == 0.5
    assert frequencies["bb"] == 0.5


def test_population_calculate_genotype_diversity(sample_creature):
    """Test calculating genotype diversity."""
    population = Population()
    
    genome1 = [None] * 1
    genome1[0] = "BB"
    creature1 = Creature(1, 0, "male", genome1, lifespan=10)
    
    genome2 = [None] * 1
    genome2[0] = "bb"
    creature2 = Creature(1, 0, "female", genome2, lifespan=10)
    
    population.add_creatures([creature1, creature2], current_cycle=0)
    
    diversity = population.calculate_genotype_diversity(0)
    assert diversity == 2

