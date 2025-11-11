"""Run the recessive trait test and generate analytics chart."""

import pytest
import sqlite3
import matplotlib.pyplot as plt
import tempfile
import yaml
from pathlib import Path
import numpy as np
from gene_sim import Simulation
from gene_sim.models.creature import Creature
from gene_sim.models.trait import Trait, Genotype, TraitType
from gene_sim.models.generation import Cycle

def run_test_and_chart():
    """Run the test and create analytics chart."""
    
    # Create config (same as test)
    config = {
        'seed': 12345,
        'years': 0.5,
        'initial_population_size': 3,
        'initial_sex_ratio': {'male': 0.33, 'female': 0.67},
        'creature_archetype': {
            'lifespan': {'min': 20, 'max': 30},
            'sexual_maturity_months': 6.0,
            'max_fertility_age_years': {'male': 10.0, 'female': 8.0},
            'gestation_period_days': 60.0,
            'nursing_period_days': 30.0,
            'menstrual_cycle_days': 28.0,
            'nearing_end_cycles': 3,
            'remove_ineligible_immediately': False,
            'litter_size': {'min': 3, 'max': 6}
        },
        'breeders': {
            'random': 1,
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
    
    try:
        # Create simulation
        sim = Simulation.from_config(config_path)
        sim.initialize()
        
        # Create specific founders: 2 BB, 1 bb
        sim.population.creatures.clear()
        sim.population.age_out = []
        
        dominant_genotype = "BB"
        recessive_genotype = "bb"
        
        genome_male_bb = [None] * 1
        genome_male_bb[0] = dominant_genotype
        
        genome_female_bb = [None] * 1
        genome_female_bb[0] = dominant_genotype
        
        genome_female_bb_recessive = [None] * 1
        genome_female_bb_recessive[0] = recessive_genotype
        
        breeder_id = sim.breeders[0].breeder_id if sim.breeders else None
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
            sexual_maturity_cycle=0,
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
            sexual_maturity_cycle=0,
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
            sexual_maturity_cycle=0,
            max_fertility_age_cycle=archetype.max_fertility_age_cycles['female'],
            generation=0
        )
        
        sim.population._persist_creatures(sim.db_conn, sim.simulation_id, [male_bb, female_bb, female_bb_recessive])
        sim.population.add_creatures([male_bb, female_bb, female_bb_recessive], current_cycle=0)
        
        # Run simulation for several cycles to get good data
        gestation_cycles = archetype.gestation_cycles
        cycles_run = 0
        max_cycles = 15  # Run enough cycles to see multiple generations
        
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
        
        # Get database path
        db_path = sim.db_path
        
        # Generate chart
        create_genotype_chart(db_path, sim.simulation_id)
        
        # Clean up
        sim.db_conn.close()
        
        return db_path
        
    finally:
        Path(config_path).unlink()

def create_genotype_chart(db_path, simulation_id):
    """Create a chart showing genotype frequencies over cycles."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all cycles from generation_stats
    cursor.execute("""
        SELECT DISTINCT generation
        FROM generation_stats
        WHERE simulation_id = ?
        ORDER BY generation
    """, (simulation_id,))
    cycles = [row[0] for row in cursor.fetchall()]
    
    # Calculate genotype frequencies by generation (when creatures are born)
    # Get all unique generations
    cursor.execute("""
        SELECT DISTINCT generation
        FROM creatures
        WHERE simulation_id = ?
        ORDER BY generation
    """, (simulation_id,))
    generations = [row[0] for row in cursor.fetchall()]
    
    genotype_data = {'BB': [], 'Bb': [], 'bb': []}
    cumulative_data = {'BB': [], 'Bb': [], 'bb': []}
    
    # Calculate frequencies per generation and cumulative
    total_so_far = {'BB': 0, 'Bb': 0, 'bb': 0}
    
    for gen in generations:
        # Count creatures in this generation
        cursor.execute("""
            SELECT cg.genotype, COUNT(*) as count
            FROM creatures c
            JOIN creature_genotypes cg ON c.creature_id = cg.creature_id AND cg.trait_id = 0
            WHERE c.simulation_id = ? AND c.generation = ?
            GROUP BY cg.genotype
        """, (simulation_id, gen))
        
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        gen_total = sum(counts.values())
        
        # Update cumulative counts
        for genotype in ['BB', 'Bb', 'bb']:
            total_so_far[genotype] += counts.get(genotype, 0)
        
        cumulative_total = sum(total_so_far.values())
        
        if gen_total > 0:
            # Per-generation frequencies
            for genotype in ['BB', 'Bb', 'bb']:
                count = counts.get(genotype, 0)
                frequency = (count / gen_total) * 100
                genotype_data[genotype].append((gen, frequency))
        
        if cumulative_total > 0:
            # Cumulative frequencies (all creatures up to this generation)
            for genotype in ['BB', 'Bb', 'bb']:
                cum_frequency = (total_so_far[genotype] / cumulative_total) * 100
                cumulative_data[genotype].append((gen, cum_frequency))
    
    # Create the chart with two subplots: per-generation and cumulative
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Plot each genotype
    colors = {'BB': '#2E86AB', 'Bb': '#A23B72', 'bb': '#F18F01'}
    labels = {'BB': 'BB (Black - Dominant Homozygous)', 
              'Bb': 'Bb (Black - Heterozygous)', 
              'bb': 'bb (Brown - Recessive Homozygous)'}
    
    # Top plot: Cumulative frequencies (all creatures up to each generation)
    for genotype in ['BB', 'Bb', 'bb']:
        if cumulative_data[genotype]:
            gens_plot = [g for g, _ in cumulative_data[genotype]]
            freqs_plot = [f for _, f in cumulative_data[genotype]]
            ax1.plot(gens_plot, freqs_plot, marker='o', label=labels[genotype], 
                    linewidth=2.5, markersize=7, color=colors[genotype], alpha=0.8)
    
    ax1.set_xlabel('Generation', fontsize=13, fontweight='bold')
    ax1.set_ylabel('Cumulative Genotype Frequency (%)', fontsize=13, fontweight='bold')
    ax1.set_title('Recessive Trait Decrease - Cumulative Genotype Frequencies by Generation\n' +
                 'Initial: 2 BB (66.7%), 1 bb (33.3%)', fontsize=15, fontweight='bold', pad=15)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend(loc='best', fontsize=11, framealpha=0.9)
    ax1.set_ylim([0, 100])
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    
    # Add annotation for initial state
    if cumulative_data['bb']:
        initial_bb = cumulative_data['bb'][0][1]
        ax1.annotate(f'Initial: bb = {initial_bb:.1f}%', 
                    xy=(0, initial_bb), xytext=(1, initial_bb + 15),
                    arrowprops=dict(arrowstyle='->', color='red', lw=2),
                    fontsize=10, fontweight='bold', color='red',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Bottom plot: Per-generation frequencies
    for genotype in ['BB', 'Bb', 'bb']:
        if genotype_data[genotype]:
            gens_plot = [g for g, _ in genotype_data[genotype]]
            freqs_plot = [f for _, f in genotype_data[genotype]]
            ax2.plot(gens_plot, freqs_plot, marker='s', label=labels[genotype], 
                    linewidth=2.5, markersize=7, color=colors[genotype], alpha=0.8)
    
    ax2.set_xlabel('Generation', fontsize=13, fontweight='bold')
    ax2.set_ylabel('Genotype Frequency in Generation (%)', fontsize=13, fontweight='bold')
    ax2.set_title('Per-Generation Genotype Frequencies', fontsize=15, fontweight='bold', pad=15)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.legend(loc='best', fontsize=11, framealpha=0.9)
    ax2.set_ylim([0, 100])
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    
    plt.tight_layout()
    
    # Save chart
    output_file = 'recessive_trait_decrease_analytics.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nChart saved to: {output_file}")
    
    # Also print analytics by generation
    print("\n" + "="*80)
    print("GENOTYPE FREQUENCIES BY GENERATION")
    print("="*80)
    for gen in generations:
        print(f"\nGeneration {gen}:")
        cursor.execute("""
            SELECT cg.genotype, COUNT(*) as count
            FROM creatures c
            JOIN creature_genotypes cg ON c.creature_id = cg.creature_id AND cg.trait_id = 0
            WHERE c.simulation_id = ? AND c.generation = ?
            GROUP BY cg.genotype
            ORDER BY cg.genotype
        """, (simulation_id, gen))
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        total = sum(counts.values())
        for genotype in ['BB', 'Bb', 'bb']:
            count = counts.get(genotype, 0)
            if total > 0:
                freq = (count / total) * 100
                print(f"  {genotype}: {freq:.2f}% ({count} creatures)")
        
        # Also show cumulative
        cursor.execute("""
            SELECT cg.genotype, COUNT(*) as count
            FROM creatures c
            JOIN creature_genotypes cg ON c.creature_id = cg.creature_id AND cg.trait_id = 0
            WHERE c.simulation_id = ? AND c.generation <= ?
            GROUP BY cg.genotype
            ORDER BY cg.genotype
        """, (simulation_id, gen))
        cum_counts = {row[0]: row[1] for row in cursor.fetchall()}
        cum_total = sum(cum_counts.values())
        if cum_total > 0:
            print(f"  Cumulative (gens 0-{gen}):")
            for genotype in ['BB', 'Bb', 'bb']:
                count = cum_counts.get(genotype, 0)
                freq = (count / cum_total) * 100
                print(f"    {genotype}: {freq:.2f}%")
    
    conn.close()

if __name__ == '__main__':
    db_path = run_test_and_chart()
    print(f"\nDatabase saved at: {db_path}")
    print("\nYou can also run: python analytics/analyze_genotypes.py")
    print("Or: python analytics/chart_phenotype.py 0")
    print("Or: python analytics/comprehensive_analytics.py")

