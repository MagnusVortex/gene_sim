"""Generation model for coordinating generation cycles."""

from dataclasses import dataclass
from typing import List, Dict, TYPE_CHECKING
import json
import sqlite3

if TYPE_CHECKING:
    from .population import Population
    from .breeder import Breeder
    from .creature import Creature
    from .trait import Trait
    from ..config import SimulationConfig


@dataclass
class GenerationStats:
    """Statistics for a single generation."""
    generation: int
    population_size: int
    eligible_males: int
    eligible_females: int
    births: int
    deaths: int
    genotype_frequencies: Dict[int, Dict[str, float]]  # trait_id -> {genotype: frequency}
    allele_frequencies: Dict[int, Dict[str, float]]  # trait_id -> {allele: frequency}
    heterozygosity: Dict[int, float]  # trait_id -> heterozygosity
    genotype_diversity: Dict[int, int]  # trait_id -> diversity count


class Generation:
    """Represents a single generation in the simulation."""
    
    def __init__(self, generation_number: int):
        """
        Initialize generation.
        
        Args:
            generation_number: Generation number (0 = founders)
        """
        self.generation_number = generation_number
    
    def execute_cycle(
        self,
        population: 'Population',
        breeders: List['Breeder'],
        traits: List['Trait'],
        rng,
        db_conn: sqlite3.Connection,
        simulation_id: int,
        config: 'SimulationConfig'
    ) -> GenerationStats:
        """
        Execute one complete generation cycle.
        
        Args:
            population: Current population working pool
            breeders: List of breeder instances
            traits: List of all traits
            rng: Random number generator
            db_conn: Database connection
            simulation_id: Simulation ID
            config: Simulation configuration
            
        Returns:
            GenerationStats object with calculated metrics
        """
        from .creature import Creature
        
        # 1. Filter eligible creatures
        eligible_males = population.get_eligible_males(self.generation_number, config)
        eligible_females = population.get_eligible_females(self.generation_number, config)
        
        # 2. Distribute breeders and select pairs
        num_pairs = min(len(eligible_males), len(eligible_females))
        if num_pairs == 0:
            # No eligible pairs, skip reproduction
            offspring = []
        else:
            # Distribute pairs to breeders
            pairs_per_breeder = num_pairs // len(breeders) if breeders else 0
            remaining_pairs = num_pairs % len(breeders) if breeders else 0
            
            all_pairs = []
            for i, breeder in enumerate(breeders):
                num_for_breeder = pairs_per_breeder + (1 if i < remaining_pairs else 0)
                if num_for_breeder > 0:
                    # Pass traits to breeders that need them
                    if hasattr(breeder, 'select_pairs'):
                        # Check if breeder needs traits parameter
                        import inspect
                        sig = inspect.signature(breeder.select_pairs)
                        if 'traits' in sig.parameters:
                            pairs = breeder.select_pairs(
                                eligible_males, eligible_females, num_for_breeder, rng, traits=traits
                            )
                        else:
                            pairs = breeder.select_pairs(
                                eligible_males, eligible_females, num_for_breeder, rng
                            )
                        all_pairs.extend(pairs)
            
            # 3. Create offspring
            offspring = []
            # Store parent references for later lookup when persisting removed offspring
            parent_map = {}  # child -> (parent1, parent2)
            
            for male, female in all_pairs:
                # Decrement female's litters_remaining
                if female.sex == 'female':
                    female.litters_remaining -= 1
                
                # Create offspring
                child = Creature.create_offspring(
                    parent1=male,
                    parent2=female,
                    birth_generation=self.generation_number + 1,
                    simulation_id=simulation_id,
                    traits=traits,
                    rng=rng,
                    max_litters=config.creature_archetype.max_litters
                )
                
                # Store parent references
                parent_map[child] = (male, female)
                
                # Update parent IDs from parent references
                # All parents should already have IDs since all creatures are persisted immediately
                if male.creature_id is None:
                    raise ValueError(
                        f"Parent1 (birth_gen={male.birth_generation}) does not have creature_id. "
                        f"All creatures must be persisted immediately upon creation."
                    )
                if female.creature_id is None:
                    raise ValueError(
                        f"Parent2 (birth_gen={female.birth_generation}) does not have creature_id. "
                        f"All creatures must be persisted immediately upon creation."
                    )
                child.parent1_id = male.creature_id
                child.parent2_id = female.creature_id
                
                # Sample lifespan from config range
                lifespan = rng.integers(
                    config.creature_archetype.lifespan_min,
                    config.creature_archetype.lifespan_max + 1
                )
                child.lifespan = lifespan
                
                offspring.append(child)
        
        # 4. Remove some offspring (sold/given away) based on removal rate
        removed_offspring = []
        remaining_offspring = []
        
        if offspring and config.creature_archetype.offspring_removal_rate > 0.0:
            for child in offspring:
                if rng.random() < config.creature_archetype.offspring_removal_rate:
                    removed_offspring.append(child)
                else:
                    remaining_offspring.append(child)
            
            # Persist removed offspring to database immediately
            # All parents should already have IDs since all creatures are persisted immediately
            if removed_offspring:
                for child in removed_offspring:
                    if child.birth_generation > 0 and child in parent_map:
                        # Get parent references
                        parent1, parent2 = parent_map[child]
                        
                        # Update parent IDs from parent references
                        # All creatures are persisted immediately, so parents must have IDs
                        if child.parent1_id is None:
                            if parent1.creature_id is None:
                                raise ValueError(
                                    f"Parent1 (birth_gen={parent1.birth_generation}) does not have creature_id. "
                                    f"All creatures must be persisted immediately upon creation."
                                )
                            child.parent1_id = parent1.creature_id
                        if child.parent2_id is None:
                            if parent2.creature_id is None:
                                raise ValueError(
                                    f"Parent2 (birth_gen={parent2.birth_generation}) does not have creature_id. "
                                    f"All creatures must be persisted immediately upon creation."
                                )
                            child.parent2_id = parent2.creature_id
                
                # Persist removed offspring immediately (all creatures are persisted upon creation)
                population._persist_creatures(db_conn, simulation_id, removed_offspring)
        else:
            remaining_offspring = offspring
        
        # 5. Persist remaining offspring immediately upon creation
        # All creatures are persisted immediately to ensure they have IDs from the start
        if remaining_offspring:
            # Update parent IDs for remaining offspring
            # All parents should already have IDs since all creatures are persisted immediately
            for child in remaining_offspring:
                if child.birth_generation > 0 and child in parent_map:
                    parent1, parent2 = parent_map[child]
                    if child.parent1_id is None:
                        if parent1.creature_id is None:
                            raise ValueError(
                                f"Parent1 (birth_gen={parent1.birth_generation}) does not have creature_id. "
                                f"All creatures must be persisted immediately upon creation."
                            )
                        child.parent1_id = parent1.creature_id
                    if child.parent2_id is None:
                        if parent2.creature_id is None:
                            raise ValueError(
                                f"Parent2 (birth_gen={parent2.birth_generation}) does not have creature_id. "
                                f"All creatures must be persisted immediately upon creation."
                            )
                        child.parent2_id = parent2.creature_id
            
            # Persist remaining offspring immediately (all creatures are persisted upon creation)
            population._persist_creatures(db_conn, simulation_id, remaining_offspring)
            
            # Now add to population (they already have IDs)
            population.add_creatures(remaining_offspring, self.generation_number + 1)
        
        # 6. Get aged-out creatures (before removal)
        aged_out = population.get_aged_out_creatures()
        
        # 7. Calculate statistics (before removal)
        genotype_frequencies = {}
        allele_frequencies = {}
        heterozygosity = {}
        genotype_diversity = {}
        
        for trait in traits:
            trait_id = trait.trait_id
            genotype_frequencies[trait_id] = population.calculate_genotype_frequencies(trait_id)
            allele_frequencies[trait_id] = population.calculate_allele_frequencies(trait_id, trait)
            heterozygosity[trait_id] = population.calculate_heterozygosity(trait_id)
            genotype_diversity[trait_id] = population.calculate_genotype_diversity(trait_id)
        
        stats = GenerationStats(
            generation=self.generation_number,
            population_size=len(population.creatures),
            eligible_males=len(eligible_males),
            eligible_females=len(eligible_females),
            births=len(offspring),  # Total births (including removed)
            deaths=len(aged_out),
            genotype_frequencies=genotype_frequencies,
            allele_frequencies=allele_frequencies,
            heterozygosity=heterozygosity,
            genotype_diversity=genotype_diversity
        )
        
        # 8. Persist generation statistics
        self._persist_generation_stats(db_conn, simulation_id, stats, traits)
        
        # 9. Remove aged-out creatures (persists them first)
        population.remove_aged_out_creatures(db_conn, simulation_id)
        
        return stats
    
    def _persist_generation_stats(
        self,
        db_conn: sqlite3.Connection,
        simulation_id: int,
        stats: GenerationStats,
        traits: List['Trait']
    ) -> None:
        """Persist generation statistics to database."""
        cursor = db_conn.cursor()
        
        # Insert generation_stats
        cursor.execute("""
            INSERT INTO generation_stats (
                simulation_id, generation, population_size,
                eligible_males, eligible_females, births, deaths
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            simulation_id,
            stats.generation,
            stats.population_size,
            stats.eligible_males,
            stats.eligible_females,
            stats.births,
            stats.deaths
        ))
        
        # Batch insert genotype frequencies
        genotype_freq_data = []
        for trait_id, frequencies in stats.genotype_frequencies.items():
            for genotype, frequency in frequencies.items():
                genotype_freq_data.append((
                    simulation_id,
                    stats.generation,
                    trait_id,
                    genotype,
                    frequency
                ))
        
        if genotype_freq_data:
            cursor.executemany("""
                INSERT INTO generation_genotype_frequencies (
                    simulation_id, generation, trait_id, genotype, frequency
                ) VALUES (?, ?, ?, ?, ?)
            """, genotype_freq_data)
        
        # Batch insert trait stats
        trait_stats_data = []
        for trait_id in [t.trait_id for t in traits]:
            allele_freqs = stats.allele_frequencies.get(trait_id, {})
            trait_stats_data.append((
                simulation_id,
                stats.generation,
                trait_id,
                json.dumps(allele_freqs),
                stats.heterozygosity.get(trait_id, 0.0),
                stats.genotype_diversity.get(trait_id, 0)
            ))
        
        if trait_stats_data:
            cursor.executemany("""
                INSERT INTO generation_trait_stats (
                    simulation_id, generation, trait_id,
                    allele_frequencies, heterozygosity, genotype_diversity
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, trait_stats_data)
        
        db_conn.commit()
    
    def advance(self) -> int:
        """
        Advance to next generation.
        
        Returns:
            New generation number
        """
        self.generation_number += 1
        return self.generation_number

