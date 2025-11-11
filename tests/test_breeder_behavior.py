"""Behavioral tests for breeder selection strategies."""

import pytest
import numpy as np
from gene_sim.models.breeder import KennelClubBreeder, MillBreeder
from gene_sim.models.creature import Creature
from gene_sim.models.trait import Trait, Genotype, TraitType


@pytest.fixture
def sample_trait():
    """Create a sample trait for testing."""
    return Trait(0, "Coat Color", TraitType.SIMPLE_MENDELIAN, [
        Genotype("BB", "Black", 0.25),
        Genotype("Bb", "Black", 0.50),
        Genotype("bb", "Brown", 0.25),
    ])


@pytest.fixture
def creatures_with_phenotypes(sample_trait):
    """Create creatures with different phenotypes."""
    # Creatures with "Black" phenotype (BB or Bb)
    black_male1 = Creature(
        simulation_id=1,
        birth_cycle=0,
        sex="male",
        genome=["BB"],
        creature_id=1,
        lifespan=100
    )
    black_male2 = Creature(
        simulation_id=1,
        birth_cycle=0,
        sex="male",
        genome=["Bb"],
        creature_id=2,
        lifespan=100
    )
    black_female1 = Creature(
        simulation_id=1,
        birth_cycle=0,
        sex="female",
        genome=["BB"],
        creature_id=3,
        lifespan=100
    )
    black_female2 = Creature(
        simulation_id=1,
        birth_cycle=0,
        sex="female",
        genome=["Bb"],
        creature_id=4,
        lifespan=100
    )
    
    # Creatures with "Brown" phenotype (bb)
    brown_male = Creature(
        simulation_id=1,
        birth_cycle=0,
        sex="male",
        genome=["bb"],
        creature_id=5,
        lifespan=100
    )
    brown_female = Creature(
        simulation_id=1,
        birth_cycle=0,
        sex="female",
        genome=["bb"],
        creature_id=6,
        lifespan=100
    )
    
    return {
        'black_males': [black_male1, black_male2],
        'black_females': [black_female1, black_female2],
        'brown_males': [brown_male],
        'brown_females': [brown_female],
        'all_males': [black_male1, black_male2, brown_male],
        'all_females': [black_female1, black_female2, brown_female],
    }


def test_kennel_club_breeder_prefers_target_phenotype(creatures_with_phenotypes, sample_trait):
    """Test that KennelClubBreeder always selects parents with target phenotype when available."""
    # Create breeder interested in "Black" phenotype
    breeder = KennelClubBreeder(
        target_phenotypes=[{'trait_id': 0, 'phenotype': 'Black'}]
    )
    
    traits = [sample_trait]
    rng = np.random.Generator(np.random.PCG64(42))
    
    # Mix of creatures with and without target phenotype
    eligible_males = creatures_with_phenotypes['all_males']  # 2 Black, 1 Brown
    eligible_females = creatures_with_phenotypes['all_females']  # 2 Black, 1 Brown
    
    # Select multiple pairs to ensure consistent behavior
    num_pairs = 10
    pairs = breeder.select_pairs(eligible_males, eligible_females, num_pairs, rng, traits)
    
    assert len(pairs) == num_pairs
    
    # Verify ALL selected pairs have the target phenotype
    for male, female in pairs:
        male_phenotype = sample_trait.get_phenotype(male.genome[0], male.sex)
        female_phenotype = sample_trait.get_phenotype(female.genome[0], female.sex)
        
        assert male_phenotype == 'Black', f"Male has phenotype {male_phenotype}, expected Black"
        assert female_phenotype == 'Black', f"Female has phenotype {female_phenotype}, expected Black"


def test_mill_breeder_prefers_target_phenotype(creatures_with_phenotypes, sample_trait):
    """Test that MillBreeder always selects parents with target phenotype when available."""
    # Create breeder interested in "Black" phenotype
    breeder = MillBreeder(
        target_phenotypes=[{'trait_id': 0, 'phenotype': 'Black'}]
    )
    
    traits = [sample_trait]
    rng = np.random.Generator(np.random.PCG64(42))
    
    # Mix of creatures with and without target phenotype
    eligible_males = creatures_with_phenotypes['all_males']  # 2 Black, 1 Brown
    eligible_females = creatures_with_phenotypes['all_females']  # 2 Black, 1 Brown
    
    # Select multiple pairs to ensure consistent behavior
    num_pairs = 10
    pairs = breeder.select_pairs(eligible_males, eligible_females, num_pairs, rng, traits)
    
    assert len(pairs) == num_pairs
    
    # Verify ALL selected pairs have the target phenotype
    for male, female in pairs:
        male_phenotype = sample_trait.get_phenotype(male.genome[0], male.sex)
        female_phenotype = sample_trait.get_phenotype(female.genome[0], female.sex)
        
        assert male_phenotype == 'Black', f"Male has phenotype {male_phenotype}, expected Black"
        assert female_phenotype == 'Black', f"Female has phenotype {female_phenotype}, expected Black"


def test_kennel_club_breeder_prefers_target_phenotype_brown(creatures_with_phenotypes, sample_trait):
    """Test that KennelClubBreeder prefers Brown phenotype when that's the target."""
    # Create breeder interested in "Brown" phenotype
    breeder = KennelClubBreeder(
        target_phenotypes=[{'trait_id': 0, 'phenotype': 'Brown'}]
    )
    
    traits = [sample_trait]
    rng = np.random.Generator(np.random.PCG64(43))  # Different seed
    
    # Mix of creatures with and without target phenotype
    eligible_males = creatures_with_phenotypes['all_males']  # 2 Black, 1 Brown
    eligible_females = creatures_with_phenotypes['all_females']  # 2 Black, 1 Brown
    
    # Select multiple pairs
    num_pairs = 10
    pairs = breeder.select_pairs(eligible_males, eligible_females, num_pairs, rng, traits)
    
    assert len(pairs) == num_pairs
    
    # Verify ALL selected pairs have the target phenotype (Brown)
    for male, female in pairs:
        male_phenotype = sample_trait.get_phenotype(male.genome[0], male.sex)
        female_phenotype = sample_trait.get_phenotype(female.genome[0], female.sex)
        
        assert male_phenotype == 'Brown', f"Male has phenotype {male_phenotype}, expected Brown"
        assert female_phenotype == 'Brown', f"Female has phenotype {female_phenotype}, expected Brown"


def test_breeder_behavior_with_multiple_traits():
    """Test breeder behavior with multiple traits."""
    # Create two traits
    trait1 = Trait(0, "Coat Color", TraitType.SIMPLE_MENDELIAN, [
        Genotype("BB", "Black", 0.5),
        Genotype("bb", "Brown", 0.5),
    ])
    trait2 = Trait(1, "Size", TraitType.SIMPLE_MENDELIAN, [
        Genotype("SS", "Small", 0.5),
        Genotype("LL", "Large", 0.5),
    ])
    
    # Create creatures with different combinations
    # Target: Black + Small
    target_male = Creature(1, 0, "male", ["BB", "SS"], creature_id=1, lifespan=100)
    target_female = Creature(1, 0, "female", ["BB", "SS"], creature_id=2, lifespan=100)
    
    # Non-target: Brown + Large
    non_target_male = Creature(1, 0, "male", ["bb", "LL"], creature_id=3, lifespan=100)
    non_target_female = Creature(1, 0, "female", ["bb", "LL"], creature_id=4, lifespan=100)
    
    # Mixed: Black + Large (doesn't match target)
    mixed_male = Creature(1, 0, "male", ["BB", "LL"], creature_id=5, lifespan=100)
    mixed_female = Creature(1, 0, "female", ["BB", "LL"], creature_id=6, lifespan=100)
    
    breeder = KennelClubBreeder(
        target_phenotypes=[
            {'trait_id': 0, 'phenotype': 'Black'},
            {'trait_id': 1, 'phenotype': 'Small'}
        ]
    )
    
    traits = [trait1, trait2]
    rng = np.random.Generator(np.random.PCG64(44))
    
    eligible_males = [target_male, non_target_male, mixed_male]
    eligible_females = [target_female, non_target_female, mixed_female]
    
    num_pairs = 10
    pairs = breeder.select_pairs(eligible_males, eligible_females, num_pairs, rng, traits)
    
    assert len(pairs) == num_pairs
    
    # Verify ALL selected pairs match BOTH target phenotypes
    for male, female in pairs:
        male_color = trait1.get_phenotype(male.genome[0], male.sex)
        male_size = trait2.get_phenotype(male.genome[1], male.sex)
        female_color = trait1.get_phenotype(female.genome[0], female.sex)
        female_size = trait2.get_phenotype(female.genome[1], female.sex)
        
        assert male_color == 'Black', f"Male color is {male_color}, expected Black"
        assert male_size == 'Small', f"Male size is {male_size}, expected Small"
        assert female_color == 'Black', f"Female color is {female_color}, expected Black"
        assert female_size == 'Small', f"Female size is {female_size}, expected Small"


def test_breeder_fallback_when_no_target_phenotype_available(creatures_with_phenotypes, sample_trait):
    """Test that breeder falls back gracefully when no creatures with target phenotype exist."""
    # Create breeder interested in a phenotype that doesn't exist
    breeder = KennelClubBreeder(
        target_phenotypes=[{'trait_id': 0, 'phenotype': 'White'}]  # No creatures have "White"
    )
    
    traits = [sample_trait]
    rng = np.random.Generator(np.random.PCG64(45))
    
    # Only creatures with Black and Brown phenotypes
    eligible_males = creatures_with_phenotypes['all_males']
    eligible_females = creatures_with_phenotypes['all_females']
    
    # Should still return pairs (fallback behavior)
    num_pairs = 5
    pairs = breeder.select_pairs(eligible_males, eligible_females, num_pairs, rng, traits)
    
    # Should return pairs even though no target phenotype exists
    assert len(pairs) == num_pairs
    
    # Pairs should be valid creatures (just not matching the non-existent target)
    for male, female in pairs:
        assert male in eligible_males
        assert female in eligible_females

