"""Integration tests for Simulation."""

import pytest
import tempfile
import yaml
from pathlib import Path
from gene_sim import Simulation


@pytest.fixture
def simple_config_file():
    """Create a simple config file for testing."""
    config = {
        'seed': 42,
        'years': 0.25,  # ~3 cycles with 28 day cycle
        'initial_population_size': 20,
        'initial_sex_ratio': {'male': 0.5, 'female': 0.5},
        'creature_archetype': {
            'lifespan': {'min': 12, 'max': 18},
            'sexual_maturity_months': 12.0,
            'max_fertility_age_years': {'male': 10.0, 'female': 8.0},
            'gestation_period_days': 90.0,
            'nursing_period_days': 60.0,
            'menstrual_cycle_days': 28.0,
            'nearing_end_cycles': 3,
            'remove_ineligible_immediately': False
        },
        'breeders': {
            'random': 5,
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
    
    # Cleanup
    Path(config_path).unlink()
    # Also clean up any database files created
    config_dir = Path(config_path).parent
    for db_file in config_dir.glob('simulation_*.db'):
        try:
            db_file.unlink()
        except PermissionError:
            pass  # File may be locked on Windows


def test_simulation_from_config(simple_config_file):
    """Test creating simulation from config."""
    sim = Simulation.from_config(simple_config_file)
    assert sim.config.seed == 42
    assert sim.config.years == 0.25
    assert sim.config.cycles > 0  # Should be calculated


def test_simulation_run(simple_config_file):
    """Test running a complete simulation."""
    sim = Simulation.from_config(simple_config_file)
    results = sim.run()
    
    assert results.status == 'completed'
    # 0.25 years * 365.25 / 28 ≈ 3 cycles
    assert results.generations_completed == 3
    assert results.simulation_id is not None
    assert results.database_path is not None
    assert results.final_population_size >= 0


def test_simulation_reproducibility(simple_config_file):
    """Test that same seed produces same results."""
    sim1 = Simulation.from_config(simple_config_file)
    results1 = sim1.run()
    
    sim2 = Simulation.from_config(simple_config_file)
    results2 = sim2.run()
    
    # Same seed should produce same final population size
    assert results1.final_population_size == results2.final_population_size


def test_simulation_database_persistence(simple_config_file):
    """Test that simulation data is persisted to database."""
    sim = Simulation.from_config(simple_config_file)
    results = sim.run()
    
    import sqlite3
    conn = sqlite3.connect(results.database_path)
    cursor = conn.cursor()
    
    # Check simulation record exists
    cursor.execute("SELECT * FROM simulations WHERE simulation_id = ?", (results.simulation_id,))
    sim_record = cursor.fetchone()
    assert sim_record is not None
    
    # Check traits were persisted
    cursor.execute("SELECT COUNT(*) FROM traits")
    trait_count = cursor.fetchone()[0]
    assert trait_count > 0
    
    # Check generation stats were persisted
    cursor.execute("SELECT COUNT(*) FROM generation_stats WHERE simulation_id = ?", (results.simulation_id,))
    gen_count = cursor.fetchone()[0]
    assert gen_count == 3  # 0.25 years ≈ 3 cycles
    
    conn.close()

