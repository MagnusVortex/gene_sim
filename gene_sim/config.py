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
    remove_ineligible_immediately: bool
    
    # Cycle-based fields
    sexual_maturity_months: float
    max_fertility_age_years: Dict[str, float]  # {'male': ..., 'female': ...}
    gestation_period_days: float
    nursing_period_days: float
    menstrual_cycle_days: float
    nearing_end_cycles: int
    
    # Litter size configuration
    litter_size_min: int
    litter_size_max: int
    
    # Converted to cycles (calculated from above)
    gestation_cycles: int
    nursing_cycles: int
    maturity_cycles: int
    max_fertility_age_cycles: Dict[str, int]
    lifespan_cycles_min: int
    lifespan_cycles_max: int


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
    mill: int
    kennel_club_config: Optional[Dict[str, Any]] = None
    # Configuration for avoiding undesirable traits
    avoid_undesirable_phenotypes: bool = False  # If True, all breeders avoid undesirable phenotypes
    avoid_undesirable_genotypes: bool = False  # If True, all breeders avoid undesirable genotypes


@dataclass
class SimulationConfig:
    """Complete simulation configuration."""
    seed: int
    years: float  # Number of years to simulate
    cycles: int  # Calculated number of cycles (derived from years)
    initial_population_size: int
    initial_sex_ratio: Dict[str, float]
    creature_archetype: CreatureArchetypeConfig
    target_phenotypes: List[Dict[str, Any]]
    undesirable_phenotypes: List[Dict[str, Any]]  # List of {trait_id, phenotype} dicts
    undesirable_genotypes: List[Dict[str, Any]]  # List of {trait_id, genotype} dicts
    breeders: BreederConfig
    traits: List[TraitConfig]
    raw_config: Dict[str, Any]  # Store raw config for database storage
    mode: str = 'quiet'  # Output mode: 'quiet', 'monitor', or 'debug'


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
    # Required top-level fields (generations/cycles handled separately)
    required_fields = [
        'seed', 'initial_population_size',
        'initial_sex_ratio', 'creature_archetype', 'breeders', 'traits'
    ]
    
    for field in required_fields:
        if field not in config:
            raise ConfigurationError(f"Missing required field: {field}")
    
    # Validate seed
    if not isinstance(config['seed'], int):
        raise ConfigurationError("seed must be an integer")
    
    # Validate years
    if 'years' not in config:
        raise ConfigurationError("Missing required field: years")
    if not isinstance(config['years'], (int, float)) or config['years'] <= 0:
        raise ConfigurationError("years must be a positive number")
    
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
    
    # Validate cycle-based fields (required)
    required_cycle_fields = [
        'sexual_maturity_months', 'max_fertility_age_years',
        'gestation_period_days', 'nursing_period_days', 'menstrual_cycle_days',
        'nearing_end_cycles', 'lifespan', 'litter_size'
    ]
    
    for field in required_cycle_fields:
        if field not in archetype:
            raise ConfigurationError(f"creature_archetype missing required field: {field}")
    
    # Validate cycle-based fields
    if True:  # All cycle-based fields are required
        # Validate lifespan (required for cycle-based, interpreted as years)
        if 'lifespan' not in archetype:
            raise ConfigurationError("creature_archetype.lifespan is required for cycle-based configuration")
        lifespan = archetype['lifespan']
        if not isinstance(lifespan, dict) or 'min' not in lifespan or 'max' not in lifespan:
            raise ConfigurationError("lifespan must contain 'min' and 'max' keys")
        if not (isinstance(lifespan['min'], (int, float)) and lifespan['min'] > 0):
            raise ConfigurationError("lifespan.min must be a positive number")
        if not (isinstance(lifespan['max'], (int, float)) and lifespan['max'] > 0):
            raise ConfigurationError("lifespan.max must be a positive number")
        if lifespan['min'] > lifespan['max']:
            raise ConfigurationError("lifespan.min must be <= lifespan.max")
        
        if not isinstance(archetype['sexual_maturity_months'], (int, float)) or archetype['sexual_maturity_months'] <= 0:
            raise ConfigurationError("sexual_maturity_months must be a positive number")
        
        max_fertility = archetype['max_fertility_age_years']
        if not isinstance(max_fertility, dict) or 'male' not in max_fertility or 'female' not in max_fertility:
            raise ConfigurationError("max_fertility_age_years must contain 'male' and 'female' keys")
        if not (isinstance(max_fertility['male'], (int, float)) and max_fertility['male'] > 0):
            raise ConfigurationError("max_fertility_age_years.male must be a positive number")
        if not (isinstance(max_fertility['female'], (int, float)) and max_fertility['female'] > 0):
            raise ConfigurationError("max_fertility_age_years.female must be a positive number")
        
        if not isinstance(archetype['gestation_period_days'], (int, float)) or archetype['gestation_period_days'] <= 0:
            raise ConfigurationError("gestation_period_days must be a positive number")
        
        if not isinstance(archetype['nursing_period_days'], (int, float)) or archetype['nursing_period_days'] < 0:
            raise ConfigurationError("nursing_period_days must be a non-negative number")
        
        if not isinstance(archetype['menstrual_cycle_days'], (int, float)) or archetype['menstrual_cycle_days'] <= 0:
            raise ConfigurationError("menstrual_cycle_days must be a positive number")
        
        if not isinstance(archetype['nearing_end_cycles'], int) or archetype['nearing_end_cycles'] < 0:
            raise ConfigurationError("nearing_end_cycles must be a non-negative integer")
        
        # Validate litter_size
        litter_size = archetype['litter_size']
        if not isinstance(litter_size, dict) or 'min' not in litter_size or 'max' not in litter_size:
            raise ConfigurationError("litter_size must contain 'min' and 'max' keys")
        if not (isinstance(litter_size['min'], int) and litter_size['min'] > 0):
            raise ConfigurationError("litter_size.min must be a positive integer")
        if not (isinstance(litter_size['max'], int) and litter_size['max'] > 0):
            raise ConfigurationError("litter_size.max must be a positive integer")
        if litter_size['min'] > litter_size['max']:
            raise ConfigurationError("litter_size.min must be <= litter_size.max")
        
        if not isinstance(archetype.get('remove_ineligible_immediately', False), bool):
            raise ConfigurationError("remove_ineligible_immediately must be a boolean")
    
    # Validate breeders
    breeders = config['breeders']
    if not isinstance(breeders, dict):
        raise ConfigurationError("breeders must be a dictionary")
    
    breeder_types = ['random', 'inbreeding_avoidance', 'kennel_club', 'mill']
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
    
    # Validate undesirable_phenotypes (optional)
    if 'undesirable_phenotypes' in config:
        if not isinstance(config['undesirable_phenotypes'], list):
            raise ConfigurationError("undesirable_phenotypes must be a list")
        for up in config['undesirable_phenotypes']:
            if not isinstance(up, dict) or 'trait_id' not in up or 'phenotype' not in up:
                raise ConfigurationError("undesirable_phenotypes entries must have 'trait_id' and 'phenotype'")
    
    # Validate undesirable_genotypes (optional)
    if 'undesirable_genotypes' in config:
        if not isinstance(config['undesirable_genotypes'], list):
            raise ConfigurationError("undesirable_genotypes must be a list")
        for ug in config['undesirable_genotypes']:
            if not isinstance(ug, dict) or 'trait_id' not in ug or 'genotype' not in ug:
                raise ConfigurationError("undesirable_genotypes entries must have 'trait_id' and 'genotype'")
    
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


def days_to_cycles(days: float, menstrual_cycle_days: float) -> int:
    """
    Convert days to cycles, rounding to nearest whole cycle.
    
    Args:
        days: Number of days
        menstrual_cycle_days: Days per menstrual cycle
        
    Returns:
        Number of cycles (rounded)
    """
    return round(days / menstrual_cycle_days)


def months_to_cycles(months: float, menstrual_cycle_days: float) -> int:
    """
    Convert months to cycles.
    
    Args:
        months: Number of months
        menstrual_cycle_days: Days per menstrual cycle
        
    Returns:
        Number of cycles (rounded)
    """
    days = months * 30.44  # Average days per month
    return days_to_cycles(days, menstrual_cycle_days)


def years_to_cycles(years: float, menstrual_cycle_days: float) -> int:
    """
    Convert years to cycles.
    
    Args:
        years: Number of years
        menstrual_cycle_days: Days per menstrual cycle
        
    Returns:
        Number of cycles (rounded)
    """
    days = years * 365.25  # Account for leap years
    return days_to_cycles(days, menstrual_cycle_days)
    return days_to_cycles(days, menstrual_cycle_days)


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
    
    # Convert cycle-based time units to cycles if present
    archetype = config.get('creature_archetype', {})
    if 'menstrual_cycle_days' in archetype:
        menstrual_cycle_days = archetype['menstrual_cycle_days']
        
        # Convert gestation period
        if 'gestation_period_days' in archetype:
            archetype['gestation_cycles'] = days_to_cycles(
                archetype['gestation_period_days'], menstrual_cycle_days
            )
        
        # Convert nursing period
        if 'nursing_period_days' in archetype:
            archetype['nursing_cycles'] = days_to_cycles(
                archetype['nursing_period_days'], menstrual_cycle_days
            )
        
        # Convert sexual maturity
        if 'sexual_maturity_months' in archetype:
            archetype['maturity_cycles'] = months_to_cycles(
                archetype['sexual_maturity_months'], menstrual_cycle_days
            )
        
        # Convert max fertility age
        if 'max_fertility_age_years' in archetype:
            max_fertility = archetype['max_fertility_age_years']
            archetype['max_fertility_age_cycles'] = {
                'male': years_to_cycles(max_fertility['male'], menstrual_cycle_days),
                'female': years_to_cycles(max_fertility['female'], menstrual_cycle_days)
            }
        
        # Convert lifespan (min/max in years) to cycles
        if 'lifespan' in archetype:
            lifespan = archetype['lifespan']
            if isinstance(lifespan, dict) and 'min' in lifespan and 'max' in lifespan:
                # Lifespan range in years, convert to cycles
                archetype['lifespan_cycles_min'] = years_to_cycles(
                    lifespan['min'], menstrual_cycle_days
                )
                archetype['lifespan_cycles_max'] = years_to_cycles(
                    lifespan['max'], menstrual_cycle_days
                )


def build_config(raw_config: Dict[str, Any]) -> SimulationConfig:
    """
    Build SimulationConfig object from validated raw config.
    
    Args:
        raw_config: Validated and normalized configuration dictionary
        
    Returns:
        SimulationConfig object
    """
    archetype = raw_config['creature_archetype']
    lifespan = archetype['lifespan']
    
    # Cycle-based configuration (only supported format)
    litter_size = archetype['litter_size']
    creature_archetype = CreatureArchetypeConfig(
        remove_ineligible_immediately=archetype.get('remove_ineligible_immediately', False),
        
        # Cycle-based fields
        sexual_maturity_months=archetype['sexual_maturity_months'],
        max_fertility_age_years=archetype['max_fertility_age_years'],
        gestation_period_days=archetype['gestation_period_days'],
        nursing_period_days=archetype['nursing_period_days'],
        menstrual_cycle_days=archetype['menstrual_cycle_days'],
        nearing_end_cycles=archetype['nearing_end_cycles'],
        
        # Litter size configuration
        litter_size_min=litter_size['min'],
        litter_size_max=litter_size['max'],
        
        # Converted cycles (calculated in normalize_config)
        gestation_cycles=archetype.get('gestation_cycles', 0),
        nursing_cycles=archetype.get('nursing_cycles', 0),
        maturity_cycles=archetype.get('maturity_cycles', 0),
        max_fertility_age_cycles=archetype.get('max_fertility_age_cycles', {'male': 0, 'female': 0}),
        lifespan_cycles_min=archetype.get('lifespan_cycles_min', 0),
        lifespan_cycles_max=archetype.get('lifespan_cycles_max', 0)
    )
    
    breeders = raw_config['breeders']
    breeder_config = BreederConfig(
        random=breeders['random'],
        inbreeding_avoidance=breeders['inbreeding_avoidance'],
        kennel_club=breeders['kennel_club'],
        mill=breeders['mill'],
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
    undesirable_phenotypes = raw_config.get('undesirable_phenotypes', [])
    undesirable_genotypes = raw_config.get('undesirable_genotypes', [])
    
    # Calculate cycles from years using menstrual cycle length
    years = raw_config['years']
    menstrual_cycle_days = archetype.get('menstrual_cycle_days', 28.0)  # Default if not set
    cycles = years_to_cycles(years, menstrual_cycle_days)
    
    # Get output mode (default to 'quiet')
    mode = raw_config.get('mode', 'quiet')
    if mode not in ['quiet', 'monitor', 'debug']:
        raise ConfigurationError(f"mode must be 'quiet', 'monitor', or 'debug', got '{mode}'")
    
    return SimulationConfig(
        seed=raw_config['seed'],
        years=years,
        cycles=cycles,
        initial_population_size=raw_config['initial_population_size'],
        initial_sex_ratio=raw_config['initial_sex_ratio'],
        creature_archetype=creature_archetype,
        target_phenotypes=target_phenotypes,
        undesirable_phenotypes=undesirable_phenotypes,
        undesirable_genotypes=undesirable_genotypes,
        breeders=breeder_config,
        traits=traits,
        raw_config=raw_config,
        mode=mode
    )

