"""Cycle model for coordinating cycle-based simulation."""

from dataclasses import dataclass
from typing import List, Dict, Optional, TYPE_CHECKING
import json
import sqlite3
import numpy as np

if TYPE_CHECKING:
    from .population import Population
    from .breeder import Breeder
    from .creature import Creature
    from .trait import Trait
    from ..config import SimulationConfig


@dataclass
class CycleStats:
    """Statistics for a single cycle."""
    cycle: int
    population_size: int
    eligible_males: int
    eligible_females: int
    births: int
    deaths: int
    genotype_frequencies: Dict[int, Dict[str, float]]  # trait_id -> {genotype: frequency}
    allele_frequencies: Dict[int, Dict[str, float]]  # trait_id -> {allele: frequency}
    heterozygosity: Dict[int, float]  # trait_id -> heterozygosity
    genotype_diversity: Dict[int, int]  # trait_id -> diversity count


class Cycle:
    """Represents a single cycle in the simulation (one menstrual cycle)."""
    
    def __init__(self, cycle_number: int):
        """
        Initialize cycle.
        
        Args:
            cycle_number: Cycle number (0 = initial state)
        """
        self.cycle_number = cycle_number
    
    def execute_cycle(
        self,
        population: 'Population',
        breeders: List['Breeder'],
        traits: List['Trait'],
        rng: np.random.Generator,
        db_conn: sqlite3.Connection,
        simulation_id: int,
        config: 'SimulationConfig'
    ) -> CycleStats:
        """
        Execute one complete cycle (one menstrual cycle).
        
        Args:
            population: Current population working pool
            breeders: List of breeder instances
            traits: List of all traits
            rng: Random number generator
            db_conn: Database connection
            simulation_id: Simulation ID
            config: Simulation configuration
            
        Returns:
            CycleStats object with calculated metrics
        """
        from .creature import Creature
        
        current_cycle = self.cycle_number
        
        # 1. Handle births (creatures born when current_cycle == birth_cycle)
        births_this_cycle = []
        for creature in list(population.creatures):
            if creature.birth_cycle == current_cycle and creature.birth_cycle > 0:
                # Creature is born this cycle
                births_this_cycle.append(creature)
                # Set nursing_end_cycle for mother if this is a new birth
                # (Note: We need to find the mother - this is handled when offspring are created)
        
        # 2. Filter eligible creatures for breeding
        # Check gestation, nursing, maturity, etc. (all creatures are fertile at the same time)
        eligible_males = population.get_eligible_males(current_cycle, config)
        eligible_females = population.get_eligible_females(current_cycle, config)
        
        # 3. Distribute breeders and select pairs
        # Track males that have mated this cycle (max 1 mate per cycle)
        mated_males = set()
        
        num_pairs = min(len(eligible_males), len(eligible_females))
        if num_pairs == 0:
            # No eligible pairs, skip reproduction
            offspring = []
        else:
            # Filter out males that have already mated this cycle
            available_males = [m for m in eligible_males if m.creature_id not in mated_males]
            num_pairs = min(len(available_males), len(eligible_females))
            
            if num_pairs == 0:
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
                                    available_males, eligible_females, num_for_breeder, rng, traits=traits
                                )
                            else:
                                pairs = breeder.select_pairs(
                                    available_males, eligible_females, num_for_breeder, rng
                                )
                            all_pairs.extend(pairs)
                
                # 4. Create offspring at conception (current_cycle)
                offspring = []
                # Store parent references for later lookup when persisting removed offspring
                parent_map = {}  # child -> (parent1, parent2)
                
                for male, female in all_pairs:
                    # Mark male as mated this cycle
                    if male.creature_id is not None:
                        mated_males.add(male.creature_id)
                    
                    # Set gestation_end_cycle for female
                    archetype = config.creature_archetype
                    female.gestation_end_cycle = current_cycle + archetype.gestation_cycles
                    
                    # Create offspring at conception
                    child = Creature.create_offspring(
                        parent1=male,
                        parent2=female,
                        conception_cycle=current_cycle,
                        simulation_id=simulation_id,
                        traits=traits,
                        rng=rng,
                        config=config
                    )
                    
                    # Store parent references
                    parent_map[child] = (male, female)
                    
                    # Update parent IDs from parent references
                    # All parents should already have IDs since all creatures are persisted immediately
                    if male.creature_id is None:
                        raise ValueError(
                            f"Parent1 (birth_cycle={male.birth_cycle}) does not have creature_id. "
                            f"All creatures must be persisted immediately upon creation."
                        )
                    if female.creature_id is None:
                        raise ValueError(
                            f"Parent2 (birth_cycle={female.birth_cycle}) does not have creature_id. "
                            f"All creatures must be persisted immediately upon creation."
                        )
                    child.parent1_id = male.creature_id
                    child.parent2_id = female.creature_id
                    
                    # Sample lifespan from config range (in cycles)
                    lifespan = rng.integers(
                        config.creature_archetype.lifespan_cycles_min,
                        config.creature_archetype.lifespan_cycles_max + 1
                    )
                    child.lifespan = lifespan
                    
                    offspring.append(child)
        
        # 5. Handle births: Set nursing_end_cycle for mothers when offspring are born
        # Note: Offspring are created at conception, but born later (when birth_cycle == current_cycle)
        # For now, we'll handle births when they occur (in step 1), but we need to set nursing periods
        # when births actually happen. Since offspring are created at conception, we need to track
        # which females gave birth this cycle and set their nursing_end_cycle.
        
        # Find females who gave birth this cycle and set nursing_end_cycle
        for child in births_this_cycle:
            if child.parent1_id is not None or child.parent2_id is not None:
                # Find the mother (female parent)
                # We need to look up parents - for now, assume parent2 is female if we can't determine
                # In practice, we'd query the database or have parent references
                # For cycle-based system, we'll set nursing when the birth actually occurs
                pass
        
        # 6. Determine which offspring to keep vs give away based on ownership rules
        # Rule: Breeder gives away ALL offspring UNLESS parent is nearing end of reproduction
        # If parent is nearing end, breeder keeps ONE offspring as replacement
        removed_offspring = []
        remaining_offspring = []
        
        # Group offspring by breeder (owner)
        offspring_by_breeder: Dict[Optional[int], List[Creature]] = {}
        for child in offspring:
            breeder_id = child.breeder_id
            if breeder_id not in offspring_by_breeder:
                offspring_by_breeder[breeder_id] = []
            offspring_by_breeder[breeder_id].append(child)
        
        # Process each breeder's offspring
        for breeder_id, breeder_offspring in offspring_by_breeder.items():
            # Check if any parent is nearing end of reproduction
            parent_nearing_end = False
            for child in breeder_offspring:
                if child in parent_map:
                    parent1, parent2 = parent_map[child]
                    # Check if either parent is nearing end (and owned by this breeder)
                    if (parent1.breeder_id == breeder_id and 
                        parent1.is_nearing_end_of_reproduction(current_cycle, config)):
                        parent_nearing_end = True
                        break
                    if (parent2.breeder_id == breeder_id and 
                        parent2.is_nearing_end_of_reproduction(current_cycle, config)):
                        parent_nearing_end = True
                        break
            
            if parent_nearing_end:
                # Keep ONE offspring as replacement, give away the rest
                if len(breeder_offspring) > 0:
                    # Keep first one, remove the rest
                    remaining_offspring.append(breeder_offspring[0])
                    removed_offspring.extend(breeder_offspring[1:])
            else:
                # Give away ALL offspring
                removed_offspring.extend(breeder_offspring)
        
        # Update parent IDs for all offspring before persisting
        all_offspring = removed_offspring + remaining_offspring
        for child in all_offspring:
            if child.birth_cycle > 0 and child in parent_map:
                parent1, parent2 = parent_map[child]
                if child.parent1_id is None:
                    if parent1.creature_id is None:
                        raise ValueError(
                            f"Parent1 (birth_cycle={parent1.birth_cycle}) does not have creature_id. "
                            f"All creatures must be persisted immediately upon creation."
                        )
                    child.parent1_id = parent1.creature_id
                if child.parent2_id is None:
                    if parent2.creature_id is None:
                        raise ValueError(
                            f"Parent2 (birth_cycle={parent2.birth_cycle}) does not have creature_id. "
                            f"All creatures must be persisted immediately upon creation."
                        )
                    child.parent2_id = parent2.creature_id
        
        # Persist removed offspring immediately (all creatures are persisted upon creation)
        if removed_offspring:
            population._persist_creatures(db_conn, simulation_id, removed_offspring)
        
        # 7. Persist remaining offspring immediately upon creation
        # All creatures are persisted immediately to ensure they have IDs from the start
        if remaining_offspring:
            # Parent IDs already updated in step 6
            # Persist remaining offspring immediately (all creatures are persisted upon creation)
            population._persist_creatures(db_conn, simulation_id, remaining_offspring)
            
            # Note: Offspring are created at conception but not added to population until birth
            # They will be added when birth_cycle == current_cycle (handled in step 1)
            # For now, we'll add them immediately for simplicity (they'll be in population but not eligible until birth)
            # Actually, according to the migration prompt, offspring are created immediately with future birth_cycle
            # So we should add them to population now, but they won't be eligible until birth
            # However, the prompt says "Create offspring object immediately with future birth_cycle"
            # So we persist them but they're not "born" until birth_cycle
            # For now, let's add them to population (they'll be tracked but not eligible)
            population.add_creatures(remaining_offspring, current_cycle)
        
        # 8. Handle ownership transfers (random events)
        # Most creatures have 2-3 owners throughout their lives
        # Simulate ownership transfers as random events
        self._handle_ownership_transfers(
            population, breeders, db_conn, simulation_id, rng
        )
        
        # 9. Get aged-out creatures (before removal)
        aged_out = population.get_aged_out_creatures()
        
        # 10. Calculate statistics (before removal)
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
        
        stats = CycleStats(
            cycle=current_cycle,
            population_size=len(population.creatures),
            eligible_males=len(eligible_males),
            eligible_females=len(eligible_females),
            births=len(births_this_cycle),  # Actual births this cycle
            deaths=len(aged_out),
            genotype_frequencies=genotype_frequencies,
            allele_frequencies=allele_frequencies,
            heterozygosity=heterozygosity,
            genotype_diversity=genotype_diversity
        )
        
        # 11. Persist cycle statistics
        self._persist_cycle_stats(db_conn, simulation_id, stats, traits)
        
        # 12. Remove aged-out creatures (they are already persisted)
        population.remove_aged_out_creatures(db_conn, simulation_id)
        
        return stats
    
    def _handle_ownership_transfers(
        self,
        population: 'Population',
        breeders: List['Breeder'],
        db_conn: sqlite3.Connection,
        simulation_id: int,
        rng: np.random.Generator
    ) -> None:
        """
        Handle random ownership transfers.
        
        Most creatures have 2-3 owners throughout their lives.
        Simulate transfers as random events with appropriate frequency.
        
        Args:
            population: Current population
            breeders: List of all breeders
            db_conn: Database connection
            simulation_id: Simulation ID
            rng: Random number generator
        """
        if not breeders:
            return
        
        cursor = db_conn.cursor()
        
        # Calculate transfer probability
        # If creatures live ~15 generations and have 2-3 owners on average,
        # that's about 1-2 transfers per creature lifetime
        # So roughly 0.1-0.15 probability per generation per creature
        # Use 0.12 as middle ground (about 1.8 transfers per 15-generation lifetime)
        transfer_probability = 0.12
        
        for creature in population.creatures:
            if creature.breeder_id is None:
                continue
            
            # Random chance of ownership transfer
            if rng.random() < transfer_probability:
                # Select new owner (random, excluding current owner)
                available_breeders = [b for b in breeders if b.breeder_id != creature.breeder_id]
                if available_breeders:
                    new_owner = rng.choice(available_breeders)
                    old_breeder_id = creature.breeder_id
                    creature.breeder_id = new_owner.breeder_id
                    
                    # Record ownership transfer in database
                    cursor.execute("""
                        INSERT INTO creature_ownership_history (
                            creature_id, breeder_id, transfer_generation
                        ) VALUES (?, ?, ?)
                    """, (creature.creature_id, new_owner.breeder_id, self.cycle_number))
                    
                    # Update creature's breeder_id in database
                    cursor.execute("""
                        UPDATE creatures
                        SET breeder_id = ?
                        WHERE creature_id = ?
                    """, (new_owner.breeder_id, creature.creature_id))
        
        db_conn.commit()
    
    def _persist_cycle_stats(
        self,
        db_conn: sqlite3.Connection,
        simulation_id: int,
        stats: CycleStats,
        traits: List['Trait']
    ) -> None:
        """Persist cycle statistics to database."""
        cursor = db_conn.cursor()
        
        # Insert generation_stats (using generation column to store cycle number)
        cursor.execute("""
            INSERT INTO generation_stats (
                simulation_id, generation, population_size,
                eligible_males, eligible_females, births, deaths
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            simulation_id,
            stats.cycle,  # Store cycle number in generation column
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
                    stats.cycle,  # Store cycle number in generation column
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
                stats.cycle,  # Store cycle number in generation column
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
        Advance to next cycle.
        
        Returns:
            New cycle number
        """
        self.cycle_number += 1
        return self.cycle_number

