"""Test that recessive trait frequency decreases after first litter with dominant majority."""

import pytest
import tempfile
import yaml
import sqlite3
from pathlib import Path
import numpy as np
from gene_sim import Simulation
from gene_sim.models.creature import Creature
from gene_sim.models.trait import Trait, Genotype, TraitType


@pytest.fixture
def config_for_recessive_test():
    """Create a config for testing recessive trait decrease."""
    config = {
        'seed': 12345,  # Fixed seed for reproducibility
        'years': 0.5,  # Enough cycles for first litter
        'initial_population_size': 3,  # Will be overridden with specific creatures
        'initial_sex_ratio': {'male': 0.33, 'female': 0.67},  # 1 male, 2 females
        'creature_archetype': {
            'lifespan': {'min': 20, 'max': 30},  # Long enough to breed
            'sexual_maturity_months': 6.0,  # Mature quickly
            'max_fertility_age_years': {'male': 10.0, 'female': 8.0},
            'gestation_period_days': 60.0,  # Short gestation
            'nursing_period_days': 30.0,  # Short nursing
            'menstrual_cycle_days': 28.0,
            'nearing_end_cycles': 3,
            'remove_ineligible_immediately': False,
            'litter_size': {'min': 3, 'max': 6}
        },
        'breeders': {
            'random': 1,  # Random breeding
            'inbreeding_avoidance': 0,
            'kennel_club': 0,
            'mill': 0
        },
        'traits': [
            {
                'trait_id': 0,
                'name': 'Coat Color',
                'trait_type': 'SIMPLE_MENDELIAN',
                'genotypes': [
                    {'genotype': 'BB', 'phenotype': 'Black', 'initial_freq': 0.33},
                    {'genotype': 'Bb', 'phenotype': 'Black', 'initial_freq': 0.33},
                    {'genotype': 'bb', 'phenotype': 'Brown', 'initial_freq': 0.34},
                ]
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        config_path = f.name
    
    yield config_path
    
    # Cleanup
    Path(config_path).unlink()
    config_dir = Path(config_path).parent
    for db_file in config_dir.glob('simulation_*.db'):
        try:
            db_file.unlink()
        except PermissionError:
            pass  # File may be locked on Windows


def test_recessive_trait_decreases_after_first_litter(config_for_recessive_test):
    """
    Test that recessive trait frequency decreases after first litter when dominant genotypes are majority.
    
    Setup:
    - Population of 3: 1 male BB, 1 female BB, 1 female bb
    - Initial frequencies: BB = 2/3 (66.7%), bb = 1/3 (33.3%)
    - After first litter: bb frequency should decrease
    - Verify with analytics that the math matches expectations
    """
    # Create simulation
    sim = Simulation.from_config(config_for_recessive_test)
    sim.initialize()
    
    # Get the trait
    trait = sim.traits[0]
    
    # Clear existing population and create specific founders
    sim.population.creatures.clear()
    sim.population.age_out = []
    
    # Create 3 founders: 2 BB (dominant homozygous), 1 bb (recessive homozygous)
    # 1 male BB, 1 female BB, 1 female bb
    dominant_genotype = "BB"
    recessive_genotype = "bb"
    
    genome_male_bb = [None] * 1
    genome_male_bb[0] = dominant_genotype
    
    genome_female_bb = [None] * 1
    genome_female_bb[0] = dominant_genotype
    
    genome_female_bb_recessive = [None] * 1
    genome_female_bb_recessive[0] = recessive_genotype
    
    # Get breeder for assignment
    breeder_id = sim.breeders[0].breeder_id if sim.breeders else None
    
    # Create creatures with long lifespans, mature immediately
    archetype = sim.config.creature_archetype
    long_lifespan = archetype.lifespan_cycles_max
    
    male_bb = Creature(
        simulation_id=sim.simulation_id,
        birth_cycle=0,
        sex='male',
        genome=genome_male_bb,
        parent1_id=None,
        parent2_id=None,
        breeder_id=breeder_id,
        inbreeding_coefficient=0.0,
        lifespan=long_lifespan,
        is_alive=True,
        sexual_maturity_cycle=0,  # Mature immediately
        max_fertility_age_cycle=archetype.max_fertility_age_cycles['male'],
        generation=0
    )
    
    female_bb = Creature(
        simulation_id=sim.simulation_id,
        birth_cycle=0,
        sex='female',
        genome=genome_female_bb,
        parent1_id=None,
        parent2_id=None,
        breeder_id=breeder_id,
        inbreeding_coefficient=0.0,
        lifespan=long_lifespan,
        is_alive=True,
        sexual_maturity_cycle=0,  # Mature immediately
        max_fertility_age_cycle=archetype.max_fertility_age_cycles['female'],
        generation=0
    )
    
    female_bb_recessive = Creature(
        simulation_id=sim.simulation_id,
        birth_cycle=0,
        sex='female',
        genome=genome_female_bb_recessive,
        parent1_id=None,
        parent2_id=None,
        breeder_id=breeder_id,
        inbreeding_coefficient=0.0,
        lifespan=long_lifespan,
        is_alive=True,
        sexual_maturity_cycle=0,  # Mature immediately
        max_fertility_age_cycle=archetype.max_fertility_age_cycles['female'],
        generation=0
    )
    
    # Persist and add to population
    sim.population._persist_creatures(sim.db_conn, sim.simulation_id, [male_bb, female_bb, female_bb_recessive])
    sim.population.add_creatures([male_bb, female_bb, female_bb_recessive], current_cycle=0)
    
    # Calculate initial genotype frequencies
    initial_genotype_freqs = sim.population.calculate_genotype_frequencies(0)
    initial_bb_freq = initial_genotype_freqs.get(recessive_genotype, 0.0)
    initial_BB_freq = initial_genotype_freqs.get(dominant_genotype, 0.0)
    
    # Verify initial state
    assert len(sim.population.creatures) == 3, "Should start with 3 creatures"
    assert initial_bb_freq == pytest.approx(1/3, abs=0.01), \
        f"Initial bb frequency should be 1/3 (33.3%), got {initial_bb_freq:.3f}"
    assert initial_BB_freq == pytest.approx(2/3, abs=0.01), \
        f"Initial BB frequency should be 2/3 (66.7%), got {initial_BB_freq:.3f}"
    
    # Run simulation until first litter is born
    gestation_cycles = archetype.gestation_cycles
    cycles_run = 0
    max_cycles = 20
    
    from gene_sim.models.generation import Cycle
    
    # Track when first litter is conceived
    first_litter_conceived = False
    first_litter_cycle = None
    
    # Run cycles until first litter is born
    while cycles_run < max_cycles:
            cycle = Cycle(cycles_run)
            cycle_stats = cycle.execute_cycle(
                sim.population,
                sim.breeders,
                sim.traits,
                sim.rng,
                sim.db_conn,
                sim.simulation_id,
                sim.config
            )
            
            cycles_run += 1
            
            # Check if we have births this cycle (first litter born)
            if cycle_stats.births > 0 and not first_litter_conceived:
                first_litter_cycle = cycles_run
                # Run one more cycle to ensure all births from first litter are processed
                if cycles_run < max_cycles:
                    Cycle(cycles_run).execute_cycle(
                        sim.population, sim.breeders, sim.traits,
                        sim.rng, sim.db_conn, sim.simulation_id, sim.config
                    )
                    cycles_run += 1
                break
            
            # Check if we've conceived offspring (first litter conceived)
            if not first_litter_conceived:
                cursor = sim.db_conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM creatures 
                    WHERE simulation_id = ? 
                    AND birth_cycle > 0
                """, (sim.simulation_id,))
                conceived_count = cursor.fetchone()[0]
                if conceived_count > 0:
                    first_litter_conceived = True
                    first_litter_cycle = cycles_run
                    # Continue until births occur
                    if cycles_run >= gestation_cycles + 1:
                        # Run until births happen
                        continue
    
    # Get final genotype frequencies from database (includes all creatures)
    cursor = sim.db_conn.cursor()
    
    # Count creatures by genotype
    cursor.execute("""
        SELECT cg.genotype, COUNT(*) as count
        FROM creature_genotypes cg
        JOIN creatures c ON cg.creature_id = c.creature_id
        WHERE c.simulation_id = ? AND cg.trait_id = 0
        GROUP BY cg.genotype
    """, (sim.simulation_id,))
    genotype_counts = {row[0]: row[1] for row in cursor.fetchall()}
    total_creatures = sum(genotype_counts.values())
    
    # Calculate final frequencies
    final_genotype_freqs = {
        genotype: count / total_creatures 
        for genotype, count in genotype_counts.items()
    }
    
    final_bb_freq = final_genotype_freqs.get(recessive_genotype, 0.0)
    final_BB_freq = final_genotype_freqs.get(dominant_genotype, 0.0)
    final_Bb_freq = final_genotype_freqs.get('Bb', 0.0)
    
    # Verify we have offspring
    assert total_creatures > 3, \
        f"Expected more than 3 creatures after breeding, got {total_creatures}"
    
    # KEY ASSERTION: Recessive trait frequency should have decreased
    assert final_bb_freq < initial_bb_freq, \
        f"Recessive trait (bb) frequency should decrease: " \
        f"started at {initial_bb_freq:.3f} ({initial_bb_freq*100:.1f}%), " \
        f"ended at {final_bb_freq:.3f} ({final_bb_freq*100:.1f}%)"
    
    # Calculate expected frequency based on breeding outcomes
    # Initial: 2 BB, 1 bb
    # Possible breeding pairs:
    #   - BB x BB: produces all BB (dominant homozygous)
    #   - BB x bb: produces all Bb (heterozygous, dominant phenotype)
    #   - bb x BB: same as above
    
    # Count offspring genotypes
    cursor.execute("""
        SELECT cg.genotype, COUNT(*) as count
        FROM creatures c
        JOIN creature_genotypes cg ON c.creature_id = cg.creature_id AND cg.trait_id = 0
        WHERE c.simulation_id = ? 
        AND c.birth_cycle > 0
        GROUP BY cg.genotype
    """, (sim.simulation_id,))
    offspring_genotype_counts = {row[0]: row[1] for row in cursor.fetchall()}
    total_offspring = sum(offspring_genotype_counts.values())
    
    # Verify analytics match expectations
    # With BB x BB breeding: all offspring are BB
    # With BB x bb breeding: all offspring are Bb (heterozygous)
    # So bb genotype can only come from bb x bb breeding, which is impossible with our setup
    
    # All offspring should be either BB or Bb (never bb from BB x bb)
    assert recessive_genotype not in offspring_genotype_counts or offspring_genotype_counts[recessive_genotype] == 0, \
        f"With BB and bb parents, no offspring should have bb genotype. " \
        f"Offspring genotypes: {offspring_genotype_counts}"
    
    # Calculate expected frequency mathematically
    # Initial population: 2 BB, 1 bb (total = 3)
    # After first litter: 3 parents + N offspring
    # If BB x BB breeds: produces N BB offspring
    #   New total: 2 BB + N BB + 1 bb = (2+N) BB, 1 bb
    #   bb frequency = 1 / (3 + N) < 1/3
    
    # If BB x bb breeds: produces N Bb offspring  
    #   New total: 2 BB + N Bb + 1 bb = 2 BB, N Bb, 1 bb
    #   bb frequency = 1 / (3 + N) < 1/3
    
    # In both cases, bb frequency decreases
    expected_bb_freq_max = 1 / (3 + total_offspring)
    
    assert final_bb_freq <= expected_bb_freq_max + 0.01, \
        f"bb frequency should be <= {expected_bb_freq_max:.3f} (1/(3+{total_offspring})), " \
        f"got {final_bb_freq:.3f}"
    
    # Get frequencies by generation for analytics
    cursor.execute("""
        SELECT c.generation, cg.genotype, COUNT(*) as count
        FROM creatures c
        JOIN creature_genotypes cg ON c.creature_id = cg.creature_id AND cg.trait_id = 0
        WHERE c.simulation_id = ?
        GROUP BY c.generation, cg.genotype
        ORDER BY c.generation, cg.genotype
    """, (sim.simulation_id,))
    
    generation_data = {}
    for gen, genotype, count in cursor.fetchall():
        if gen not in generation_data:
            generation_data[gen] = {}
        generation_data[gen][genotype] = count
    
    # Calculate frequencies per generation
    generation_freqs = {}
    for gen, counts in generation_data.items():
        total = sum(counts.values())
        generation_freqs[gen] = {
            genotype: count / total 
            for genotype, count in counts.items()
        }
    
    # Print analytics summary
    print(f"\n{'='*80}")
    print("RECESSIVE TRAIT DECREASE ANALYTICS")
    print(f"{'='*80}")
    print(f"Generation 0 (Founders): 3 creatures")
    print(f"  - BB (dominant): 2 ({initial_BB_freq*100:.1f}%)")
    print(f"  - bb (recessive): 1 ({initial_bb_freq*100:.1f}%)")
    
    # Show generation 1 (first litter)
    if 1 in generation_freqs:
        gen1_freqs = generation_freqs[1]
        gen1_total = sum(generation_data[1].values())
        gen1_bb_freq = gen1_freqs.get(recessive_genotype, 0.0)
        gen1_BB_freq = gen1_freqs.get(dominant_genotype, 0.0)
        gen1_Bb_freq = gen1_freqs.get('Bb', 0.0)
        print(f"\nGeneration 1 (First Litter): {gen1_total} creatures")
        print(f"  - BB frequency: {gen1_BB_freq*100:.1f}% ({generation_data[1].get('BB', 0)} creatures)")
        print(f"  - Bb frequency: {gen1_Bb_freq*100:.1f}% ({generation_data[1].get('Bb', 0)} creatures)")
        print(f"  - bb frequency: {gen1_bb_freq*100:.1f}% ({generation_data[1].get('bb', 0)} creatures)")
    
    # Show generation 2 if it exists
    if 2 in generation_freqs:
        gen2_freqs = generation_freqs[2]
        gen2_total = sum(generation_data[2].values())
        gen2_bb_freq = gen2_freqs.get(recessive_genotype, 0.0)
        gen2_BB_freq = gen2_freqs.get(dominant_genotype, 0.0)
        gen2_Bb_freq = gen2_freqs.get('Bb', 0.0)
        print(f"\nGeneration 2: {gen2_total} creatures")
        print(f"  - BB frequency: {gen2_BB_freq*100:.1f}% ({generation_data[2].get('BB', 0)} creatures)")
        print(f"  - Bb frequency: {gen2_Bb_freq*100:.1f}% ({generation_data[2].get('Bb', 0)} creatures)")
        print(f"  - bb frequency: {gen2_bb_freq*100:.1f}% ({generation_data[2].get('bb', 0)} creatures)")
    
    print(f"\nOverall (All Generations Combined):")
    print(f"  - Total creatures: {total_creatures}")
    print(f"  - Offspring created: {total_offspring}")
    print(f"  - BB frequency: {final_BB_freq*100:.1f}% ({genotype_counts.get('BB', 0)} creatures)")
    print(f"  - Bb frequency: {final_Bb_freq*100:.1f}% ({genotype_counts.get('Bb', 0)} creatures)")
    print(f"  - bb frequency: {final_bb_freq*100:.1f}% ({genotype_counts.get('bb', 0)} creatures)")
    print(f"\nRecessive Trait Frequency Decrease:")
    print(f"  - Generation 0 (Founders): {initial_bb_freq*100:.2f}%")
    if 1 in generation_freqs:
        gen1_bb = generation_freqs[1].get(recessive_genotype, 0.0)
        print(f"  - Generation 1: {gen1_bb*100:.2f}% (decrease: {(initial_bb_freq - gen1_bb)*100:.2f} pp)")
    if 2 in generation_freqs:
        gen2_bb = generation_freqs[2].get(recessive_genotype, 0.0)
        gen1_bb = generation_freqs[1].get(recessive_genotype, 0.0) if 1 in generation_freqs else initial_bb_freq
        print(f"  - Generation 2: {gen2_bb*100:.2f}% (decrease: {(gen1_bb - gen2_bb)*100:.2f} pp from gen 1)")
    print(f"  - Final (all gens): {final_bb_freq*100:.2f}% (total decrease: {(initial_bb_freq - final_bb_freq)*100:.2f} pp)")
    print(f"  - Expected max frequency: {expected_bb_freq_max*100:.2f}%")
    print(f"  - PASS: Recessive trait frequency decreased in first two generations as expected")
    print(f"{'='*80}\n")
    
    # Additional assertion: verify decrease in generation 1
    if 1 in generation_freqs:
        gen1_bb_freq = generation_freqs[1].get(recessive_genotype, 0.0)
        assert gen1_bb_freq < initial_bb_freq, \
            f"bb frequency should decrease in generation 1: " \
            f"gen 0 = {initial_bb_freq:.3f}, gen 1 = {gen1_bb_freq:.3f}"
    
    # Additional assertion: verify decrease in generation 2 (if it exists)
    if 2 in generation_freqs:
        gen2_bb_freq = generation_freqs[2].get(recessive_genotype, 0.0)
        gen1_bb_freq = generation_freqs[1].get(recessive_genotype, 0.0) if 1 in generation_freqs else initial_bb_freq
        assert gen2_bb_freq <= gen1_bb_freq, \
            f"bb frequency should not increase in generation 2: " \
            f"gen 1 = {gen1_bb_freq:.3f}, gen 2 = {gen2_bb_freq:.3f}"
    
    # Clean up
    sim.db_conn.close()

