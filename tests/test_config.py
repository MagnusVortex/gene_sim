"""Tests for configuration system."""

import pytest
import tempfile
import yaml
from pathlib import Path
from gene_sim.config import load_config, ConfigurationError


@pytest.fixture
def sample_config():
    """Create a sample configuration."""
    return {
        'seed': 42,
        'cycles': 10,
        'initial_population_size': 100,
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
            'random': 10,
            'inbreeding_avoidance': 5,
            'kennel_club': 3,
            'unrestricted_phenotype': 2
        },
        'traits': [
            {
                'trait_id': 0,
                'name': 'Coat Color',
                'trait_type': 'SIMPLE_MENDELIAN',
                'genotypes': [
                    {'genotype': 'BB', 'phenotype': 'Black', 'initial_freq': 0.36},
                    {'genotype': 'Bb', 'phenotype': 'Black', 'initial_freq': 0.48},
                    {'genotype': 'bb', 'phenotype': 'Brown', 'initial_freq': 0.16},
                ]
            }
        ]
    }


def test_load_config_yaml(sample_config):
    """Test loading YAML configuration."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_config, f)
        config_path = f.name
    
    try:
        config = load_config(config_path)
        assert config.seed == 42
        assert config.cycles == 10
        assert config.initial_population_size == 100
        assert len(config.traits) == 1
    finally:
        Path(config_path).unlink()


def test_load_config_missing_field(sample_config):
    """Test that missing required fields raise errors."""
    del sample_config['seed']
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_config, f)
        config_path = f.name
    
    try:
        with pytest.raises(ConfigurationError):
            load_config(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_invalid_trait_id(sample_config):
    """Test that invalid trait_id raises error."""
    sample_config['traits'][0]['trait_id'] = 100  # Invalid
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_config, f)
        config_path = f.name
    
    try:
        with pytest.raises(ConfigurationError):
            load_config(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_normalizes_frequencies(sample_config):
    """Test that genotype frequencies are normalized."""
    # Use non-normalized frequencies
    sample_config['traits'][0]['genotypes'][0]['initial_freq'] = 36
    sample_config['traits'][0]['genotypes'][1]['initial_freq'] = 48
    sample_config['traits'][0]['genotypes'][2]['initial_freq'] = 16
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_config, f)
        config_path = f.name
    
    try:
        config = load_config(config_path)
        # Frequencies should be normalized
        total = sum(g['initial_freq'] for g in config.traits[0].genotypes)
        assert abs(total - 1.0) < 0.001
    finally:
        Path(config_path).unlink()

