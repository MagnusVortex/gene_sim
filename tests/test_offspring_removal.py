"""Tests for offspring removal functionality."""

import pytest
import tempfile
import yaml
import sqlite3
from pathlib import Path
from gene_sim import Simulation


@pytest.fixture
def config_with_removal():
    """Create a config with offspring removal enabled."""
    config = {
        'seed': 42,
        'generations': 5,
        'initial_population_size': 50,
        'initial_sex_ratio': {'male': 0.5, 'female': 0.5},
        'creature_archetype': {
            'max_breeding_age': {'male': 10, 'female': 8},
            'max_litters': 5,
            'lifespan': {'min': 12, 'max': 18},
            'remove_ineligible_immediately': False,
            'offspring_removal_rate': 0.5  # 50% removal rate
        },
        'breeders': {
            'random': 5,
            'inbreeding_avoidance': 0,
            'kennel_club': 0,
            'unrestricted_phenotype': 0
        },
        'traits': [
            {
                'trait_id': 0,
                'name': 'Coat Color',
                'trait_type': 'SIMPLE_MENDELIAN',
                'genotypes': [
                    {'genotype': 'BB', 'phenotype': 'Black', 'initial_freq': 0.25},
                    {'genotype': 'Bb', 'phenotype': 'Black', 'initial_freq': 0.50},
                    {'genotype': 'bb', 'phenotype': 'Brown', 'initial_freq': 0.25},
                ]
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        config_path = f.name
    
    yield config_path
    
    Path(config_path).unlink()
    config_dir = Path(config_path).parent
    for db_file in config_dir.glob('simulation_*.db'):
        db_file.unlink()


def test_offspring_removal_persists_to_db(config_with_removal):
    """Test that removed offspring are persisted to database."""
    sim = Simulation.from_config(config_with_removal)
    results = sim.run()
    
    conn = sqlite3.connect(results.database_path)
    cursor = conn.cursor()
    
    # Get total births and final population
    cursor.execute("""
        SELECT SUM(births) as total_births, 
               MAX(generation) as last_gen
        FROM generation_stats
        WHERE simulation_id = ?
    """, (results.simulation_id,))
    total_births, last_gen = cursor.fetchone()
    
    # Get population size at last generation
    cursor.execute("""
        SELECT population_size
        FROM generation_stats
        WHERE simulation_id = ? AND generation = ?
    """, (results.simulation_id, last_gen))
    final_pop = cursor.fetchone()[0]
    
    # Count creatures in database (including removed ones)
    cursor.execute("""
        SELECT COUNT(*)
        FROM creatures
        WHERE simulation_id = ? AND birth_generation > 0
    """, (results.simulation_id,))
    db_creatures = cursor.fetchone()[0]
    
    # With 50% removal rate, we expect roughly half the births to be in the final population
    # (plus initial population, minus deaths)
    # But removed offspring should still be in database
    assert db_creatures >= total_births * 0.4  # At least some removed ones persisted
    assert final_pop < total_births  # Population should be less than total births
    
    conn.close()


def test_offspring_removal_rate_zero(config_with_removal):
    """Test that removal rate of 0.0 doesn't remove any offspring."""
    # Modify config to have 0 removal rate
    import yaml
    with open(config_with_removal, 'r') as f:
        config = yaml.safe_load(f)
    config['creature_archetype']['offspring_removal_rate'] = 0.0
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        config_path = f.name
    
    try:
        sim = Simulation.from_config(config_path)
        results = sim.run()
        
        conn = sqlite3.connect(results.database_path)
        cursor = conn.cursor()
        
        # Get total births
        cursor.execute("""
            SELECT SUM(births) as total_births
            FROM generation_stats
            WHERE simulation_id = ?
        """, (results.simulation_id,))
        total_births = cursor.fetchone()[0]
        
        # All births should be in final population (minus deaths)
        # With removal rate 0, population should grow more
        assert results.final_population_size >= total_births * 0.5
        
        conn.close()
    finally:
        Path(config_path).unlink()

