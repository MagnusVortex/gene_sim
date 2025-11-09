"""Configuration loading and validation for gene_sim."""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .exceptions import ConfigurationError


@dataclass
class CreatureArchetypeConfig:
    """Configuration for creature archetype parameters."""
    max_breeding_age_male: int
    max_breeding_age_female: int
    max_litters: int
    lifespan_min: int
    lifespan_max: int
    remove_ineligible_immediately: bool
    offspring_removal_rate: float  # Probability (0.0-1.0) that offspring are removed (sold/given away)


@dataclass
class TraitConfig:
    """Configuration for a single trait."""
    trait_id: int
    name: str
    trait_type: str
    genotypes: List[Dict[str, Any]]


@dataclass
class BreederConfig:
    """Configuration for breeder distribution."""
    random: int
    inbreeding_avoidance: int
    kennel_club: int
    unrestricted_phenotype: int
    kennel_club_config: Optional[Dict[str, Any]] = None


@dataclass
class SimulationConfig:
    """Complete simulation configuration."""
    seed: int
    generations: int
    initial_population_size: int
    initial_sex_ratio: Dict[str, float]
    creature_archetype: CreatureArchetypeConfig
    target_phenotypes: List[Dict[str, Any]]
    breeders: BreederConfig
    traits: List[TraitConfig]
    raw_config: Dict[str, Any]  # Store raw config for database storage


def load_config(config_path: str) -> SimulationConfig:
    """
    Load and validate configuration from YAML or JSON file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Validated SimulationConfig object
        
    Raises:
        ConfigurationError: If file doesn't exist or configuration is invalid
    """
    path = Path(config_path)
    
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")
    
    # Load config file
    try:
        with open(path, 'r') as f:
            if path.suffix.lower() == '.json':
                raw_config = json.load(f)
            else:
                raw_config = yaml.safe_load(f)
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise ConfigurationError(f"Failed to parse configuration file: {e}") from e
    except Exception as e:
        raise ConfigurationError(f"Failed to read configuration file: {e}") from e
    
    # Validate and normalize
    validate_config(raw_config)
    normalize_config(raw_config)
    
    # Build SimulationConfig object
    return build_config(raw_config)


def validate_config(config: Dict[str, Any]) -> None:
    """
    Validate configuration structure and values.
    
    Args:
        config: Raw configuration dictionary
        
    Raises:
        ConfigurationError: If validation fails
    """
    # Required top-level fields
    required_fields = [
        'seed', 'generations', 'initial_population_size',
        'initial_sex_ratio', 'creature_archetype', 'breeders', 'traits'
    ]
    
    for field in required_fields:
        if field not in config:
            raise ConfigurationError(f"Missing required field: {field}")
    
    # Validate seed
    if not isinstance(config['seed'], int):
        raise ConfigurationError("seed must be an integer")
    
    # Validate generations
    if not isinstance(config['generations'], int) or config['generations'] < 1:
        raise ConfigurationError("generations must be a positive integer")
    
    # Validate initial_population_size
    if not isinstance(config['initial_population_size'], int) or config['initial_population_size'] < 1:
        raise ConfigurationError("initial_population_size must be a positive integer")
    
    # Validate initial_sex_ratio
    sex_ratio = config['initial_sex_ratio']
    if not isinstance(sex_ratio, dict):
        raise ConfigurationError("initial_sex_ratio must be a dictionary")
    if 'male' not in sex_ratio or 'female' not in sex_ratio:
        raise ConfigurationError("initial_sex_ratio must contain 'male' and 'female' keys")
    if not (0 <= sex_ratio['male'] <= 1 and 0 <= sex_ratio['female'] <= 1):
        raise ConfigurationError("initial_sex_ratio values must be between 0 and 1")
    
    # Validate creature_archetype
    archetype = config['creature_archetype']
    if not isinstance(archetype, dict):
        raise ConfigurationError("creature_archetype must be a dictionary")
    
    required_archetype_fields = ['max_breeding_age', 'max_litters', 'lifespan', 'remove_ineligible_immediately']
    for field in required_archetype_fields:
        if field not in archetype:
            raise ConfigurationError(f"creature_archetype missing required field: {field}")
    
    # Validate offspring_removal_rate (optional, defaults to 0.0)
    if 'offspring_removal_rate' not in archetype:
        archetype['offspring_removal_rate'] = 0.0  # Default: no removal
    else:
        removal_rate = archetype['offspring_removal_rate']
        if not isinstance(removal_rate, (int, float)) or not (0.0 <= removal_rate <= 1.0):
            raise ConfigurationError("offspring_removal_rate must be a number between 0.0 and 1.0")
    
    max_age = archetype['max_breeding_age']
    if not isinstance(max_age, dict) or 'male' not in max_age or 'female' not in max_age:
        raise ConfigurationError("max_breeding_age must contain 'male' and 'female' keys")
    if not (isinstance(max_age['male'], int) and max_age['male'] > 0):
        raise ConfigurationError("max_breeding_age.male must be a positive integer")
    if not (isinstance(max_age['female'], int) and max_age['female'] > 0):
        raise ConfigurationError("max_breeding_age.female must be a positive integer")
    
    if not isinstance(archetype['max_litters'], int) or archetype['max_litters'] < 0:
        raise ConfigurationError("max_litters must be a non-negative integer")
    
    lifespan = archetype['lifespan']
    if not isinstance(lifespan, dict) or 'min' not in lifespan or 'max' not in lifespan:
        raise ConfigurationError("lifespan must contain 'min' and 'max' keys")
    if not (isinstance(lifespan['min'], int) and lifespan['min'] > 0):
        raise ConfigurationError("lifespan.min must be a positive integer")
    if not (isinstance(lifespan['max'], int) and lifespan['max'] > 0):
        raise ConfigurationError("lifespan.max must be a positive integer")
    if lifespan['min'] > lifespan['max']:
        raise ConfigurationError("lifespan.min must be <= lifespan.max")
    
    if not isinstance(archetype['remove_ineligible_immediately'], bool):
        raise ConfigurationError("remove_ineligible_immediately must be a boolean")
    
    # Validate breeders
    breeders = config['breeders']
    if not isinstance(breeders, dict):
        raise ConfigurationError("breeders must be a dictionary")
    
    breeder_types = ['random', 'inbreeding_avoidance', 'kennel_club', 'unrestricted_phenotype']
    for breeder_type in breeder_types:
        if breeder_type not in breeders:
            raise ConfigurationError(f"breeders missing required field: {breeder_type}")
        if not isinstance(breeders[breeder_type], int) or breeders[breeder_type] < 0:
            raise ConfigurationError(f"breeders.{breeder_type} must be a non-negative integer")
    
    # Validate target_phenotypes (optional)
    if 'target_phenotypes' in config:
        if not isinstance(config['target_phenotypes'], list):
            raise ConfigurationError("target_phenotypes must be a list")
        for tp in config['target_phenotypes']:
            if not isinstance(tp, dict) or 'trait_id' not in tp or 'phenotype' not in tp:
                raise ConfigurationError("target_phenotypes entries must have 'trait_id' and 'phenotype'")
    
    # Validate traits
    if not isinstance(config['traits'], list) or len(config['traits']) == 0:
        raise ConfigurationError("traits must be a non-empty list")
    
    trait_ids = set()
    valid_trait_types = [
        'SIMPLE_MENDELIAN', 'INCOMPLETE_DOMINANCE', 'CODOMINANCE',
        'SEX_LINKED', 'POLYGENIC'
    ]
    
    for trait in config['traits']:
        if not isinstance(trait, dict):
            raise ConfigurationError("Each trait must be a dictionary")
        
        if 'trait_id' not in trait:
            raise ConfigurationError("Trait missing required field: trait_id")
        trait_id = trait['trait_id']
        if not isinstance(trait_id, int) or not (0 <= trait_id < 100):
            raise ConfigurationError(f"trait_id must be an integer between 0 and 99, got {trait_id}")
        if trait_id in trait_ids:
            raise ConfigurationError(f"Duplicate trait_id: {trait_id}")
        trait_ids.add(trait_id)
        
        if 'name' not in trait or not isinstance(trait['name'], str):
            raise ConfigurationError(f"Trait {trait_id} missing or invalid 'name' field")
        
        if 'trait_type' not in trait or trait['trait_type'] not in valid_trait_types:
            raise ConfigurationError(f"Trait {trait_id} has invalid trait_type: {trait.get('trait_type')}")
        
        if 'genotypes' not in trait or not isinstance(trait['genotypes'], list) or len(trait['genotypes']) == 0:
            raise ConfigurationError(f"Trait {trait_id} must have a non-empty genotypes list")
        
        genotype_strings = set()
        for genotype in trait['genotypes']:
            if not isinstance(genotype, dict):
                raise ConfigurationError(f"Trait {trait_id} genotype must be a dictionary")
            
            if 'genotype' not in genotype or 'phenotype' not in genotype or 'initial_freq' not in genotype:
                raise ConfigurationError(f"Trait {trait_id} genotype missing required fields")
            
            genotype_str = genotype['genotype']
            if genotype_str in genotype_strings:
                raise ConfigurationError(f"Trait {trait_id} has duplicate genotype: {genotype_str}")
            genotype_strings.add(genotype_str)
            
            if not isinstance(genotype['initial_freq'], (int, float)) or genotype['initial_freq'] < 0:
                raise ConfigurationError(f"Trait {trait_id} genotype {genotype_str} has invalid initial_freq")
            
            # Validate sex field for sex-linked traits
            if trait['trait_type'] == 'SEX_LINKED':
                if 'sex' not in genotype:
                    raise ConfigurationError(f"Trait {trait_id} (SEX_LINKED) genotype {genotype_str} missing 'sex' field")
                if genotype['sex'] not in ['male', 'female']:
                    raise ConfigurationError(f"Trait {trait_id} genotype {genotype_str} has invalid sex: {genotype['sex']}")


def normalize_config(config: Dict[str, Any]) -> None:
    """
    Normalize configuration values (e.g., normalize genotype frequencies).
    
    Args:
        config: Configuration dictionary (modified in place)
    """
    # Normalize sex ratio to sum to 1.0
    sex_ratio = config['initial_sex_ratio']
    total = sex_ratio['male'] + sex_ratio['female']
    if total > 0:
        sex_ratio['male'] /= total
        sex_ratio['female'] /= total
    
    # Normalize genotype frequencies for each trait
    for trait in config['traits']:
        genotypes = trait['genotypes']
        total_freq = sum(g['initial_freq'] for g in genotypes)
        
        if total_freq == 0:
            raise ConfigurationError(f"Trait {trait['trait_id']} has zero total frequency")
        
        # Normalize frequencies
        for genotype in genotypes:
            genotype['initial_freq'] /= total_freq


def build_config(raw_config: Dict[str, Any]) -> SimulationConfig:
    """
    Build SimulationConfig object from validated raw config.
    
    Args:
        raw_config: Validated and normalized configuration dictionary
        
    Returns:
        SimulationConfig object
    """
    archetype = raw_config['creature_archetype']
    creature_archetype = CreatureArchetypeConfig(
        max_breeding_age_male=archetype['max_breeding_age']['male'],
        max_breeding_age_female=archetype['max_breeding_age']['female'],
        max_litters=archetype['max_litters'],
        lifespan_min=archetype['lifespan']['min'],
        lifespan_max=archetype['lifespan']['max'],
        remove_ineligible_immediately=archetype['remove_ineligible_immediately'],
        offspring_removal_rate=archetype.get('offspring_removal_rate', 0.0)
    )
    
    breeders = raw_config['breeders']
    breeder_config = BreederConfig(
        random=breeders['random'],
        inbreeding_avoidance=breeders['inbreeding_avoidance'],
        kennel_club=breeders['kennel_club'],
        unrestricted_phenotype=breeders['unrestricted_phenotype'],
        kennel_club_config=breeders.get('kennel_club_config')
    )
    
    traits = [
        TraitConfig(
            trait_id=t['trait_id'],
            name=t['name'],
            trait_type=t['trait_type'],
            genotypes=t['genotypes']
        )
        for t in raw_config['traits']
    ]
    
    target_phenotypes = raw_config.get('target_phenotypes', [])
    
    return SimulationConfig(
        seed=raw_config['seed'],
        generations=raw_config['generations'],
        initial_population_size=raw_config['initial_population_size'],
        initial_sex_ratio=raw_config['initial_sex_ratio'],
        creature_archetype=creature_archetype,
        target_phenotypes=target_phenotypes,
        breeders=breeder_config,
        traits=traits,
        raw_config=raw_config
    )

