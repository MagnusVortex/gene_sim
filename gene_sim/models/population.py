"""Population model for managing working pool of creatures."""

from typing import List, Dict, Optional, TYPE_CHECKING
from .creature import Creature

if TYPE_CHECKING:
    from ..config import SimulationConfig


class Population:
    """Manages the working pool of creatures and aging-out list."""
    
    def __init__(self):
        """Initialize empty population."""
        self.creatures: List[Creature] = []
        # Aging-out list: List[List[Creature]] where index 0 = current cycle
        self.age_out: List[List[Creature]] = []
    
    def get_eligible_males(
        self, 
        current_cycle: int, 
        config: 'SimulationConfig'
    ) -> List[Creature]:
        """
        Get list of eligible male creatures for breeding.
        
        Args:
            current_cycle: Current simulation cycle
            config: Simulation configuration
            
        Returns:
            List of eligible male creatures
        """
        return [
            c for c in self.creatures
            if c.sex == 'male' and c.is_breeding_eligible(current_cycle, config)
        ]
    
    def get_eligible_females(
        self, 
        current_cycle: int, 
        config: 'SimulationConfig'
    ) -> List[Creature]:
        """
        Get list of eligible female creatures for breeding.
        
        Args:
            current_cycle: Current simulation cycle
            config: Simulation configuration
            
        Returns:
            List of eligible female creatures
        """
        return [
            c for c in self.creatures
            if c.sex == 'female' and c.is_breeding_eligible(current_cycle, config)
        ]
    
    def add_creatures(self, creatures: List[Creature], current_cycle: int) -> None:
        """
        Add new creatures to the working pool and update aging-out list.
        
        Args:
            creatures: List of creatures to add
            current_cycle: Current simulation cycle
        """
        self.creatures.extend(creatures)
        
        # Update aging-out list
        for creature in creatures:
            # Calculate relative cycle when creature will age out
            # Age out when: current_cycle >= birth_cycle + lifespan
            relative_cycle = creature.birth_cycle + creature.lifespan - current_cycle
            
            # Ensure aging-out list is large enough
            while len(self.age_out) <= relative_cycle:
                self.age_out.append([])
            
            # Append creature to appropriate cycle slot
            self.age_out[relative_cycle].append(creature)
    
    def get_aged_out_creatures(self) -> List[Creature]:
        """
        Get creatures who age out in the current cycle.
        
        Returns:
            List of creatures aging out (from age_out[0])
        """
        if len(self.age_out) == 0:
            return []
        return self.age_out[0].copy() if self.age_out[0] else []
    
    def remove_aged_out_creatures(self, db_conn, simulation_id: int) -> None:
        """
        Remove aged-out creatures from working pool.
        
        Note: All creatures are already persisted immediately upon creation,
        so this method only removes them from the in-memory working pool.
        
        Args:
            db_conn: Database connection (unused, kept for API compatibility)
            simulation_id: Simulation ID (unused, kept for API compatibility)
        """
        aged_out = self.get_aged_out_creatures()
        if not aged_out:
            return
        
        # All creatures are already persisted immediately upon creation,
        # so we only need to remove them from the working pool
        creature_ids_to_remove = {c.creature_id for c in aged_out if c.creature_id is not None}
        self.creatures = [c for c in self.creatures if c.creature_id not in creature_ids_to_remove]
        
        # Slice off age_out[0]
        if len(self.age_out) > 0:
            self.age_out = self.age_out[1:]
    
    def advance_cycle(self) -> None:
        """
        Advance aging-out list by slicing off the first element.
        Should be called after remove_aged_out_creatures.
        """
        if len(self.age_out) > 0:
            self.age_out = self.age_out[1:]
    
    def calculate_genotype_frequencies(self, trait_id: int) -> Dict[str, float]:
        """
        Calculate genotype frequencies for a given trait.
        
        Args:
            trait_id: ID of the trait
            
        Returns:
            Dictionary mapping genotype strings to frequencies
        """
        if not self.creatures:
            return {}
        
        genotype_counts: Dict[str, int] = {}
        total = 0
        
        for creature in self.creatures:
            if trait_id < len(creature.genome) and creature.genome[trait_id] is not None:
                genotype = creature.genome[trait_id]
                genotype_counts[genotype] = genotype_counts.get(genotype, 0) + 1
                total += 1
        
        if total == 0:
            return {}
        
        return {genotype: count / total for genotype, count in genotype_counts.items()}
    
    def calculate_allele_frequencies(self, trait_id: int, trait) -> Dict[str, float]:
        """
        Calculate allele frequencies for a given trait.
        
        Args:
            trait_id: ID of the trait
            trait: Trait object with genotype information
            
        Returns:
            Dictionary mapping allele strings to frequencies
        """
        if not self.creatures:
            return {}
        
        allele_counts: Dict[str, int] = {}
        total_alleles = 0
        
        for creature in self.creatures:
            if trait_id >= len(creature.genome) or creature.genome[trait_id] is None:
                continue
            
            genotype_str = creature.genome[trait_id]
            
            # Extract alleles based on trait type
            if trait.trait_type.value == 'SEX_LINKED':
                if creature.sex == 'male':
                    # Male has single allele
                    allele = genotype_str
                    allele_counts[allele] = allele_counts.get(allele, 0) + 1
                    total_alleles += 1
                else:
                    # Female has two alleles
                    if len(genotype_str) == 2:
                        for allele in genotype_str:
                            allele_counts[allele] = allele_counts.get(allele, 0) + 1
                            total_alleles += 1
                    else:
                        # Handle multi-character alleles (e.g., "Nc")
                        # Simplified: treat as single allele for now
                        allele_counts[genotype_str] = allele_counts.get(genotype_str, 0) + 1
                        total_alleles += 1
            else:
                # Non-sex-linked: extract alleles
                if '_' in genotype_str:
                    # Polygenic: extract from each gene pair
                    gene_pairs = genotype_str.split('_')
                    for pair in gene_pairs:
                        if len(pair) >= 2:
                            mid = len(pair) // 2
                            allele1 = pair[:mid]
                            allele2 = pair[mid:]
                            allele_counts[allele1] = allele_counts.get(allele1, 0) + 1
                            allele_counts[allele2] = allele_counts.get(allele2, 0) + 1
                            total_alleles += 2
                else:
                    # Simple: extract two alleles
                    if len(genotype_str) == 2:
                        for allele in genotype_str:
                            allele_counts[allele] = allele_counts.get(allele, 0) + 1
                            total_alleles += 1
                    else:
                        # Handle longer genotypes
                        mid = len(genotype_str) // 2
                        allele1 = genotype_str[:mid]
                        allele2 = genotype_str[mid:]
                        allele_counts[allele1] = allele_counts.get(allele1, 0) + 1
                        allele_counts[allele2] = allele_counts.get(allele2, 0) + 1
                        total_alleles += 1
        
        if total_alleles == 0:
            return {}
        
        return {allele: count / total_alleles for allele, count in allele_counts.items()}
    
    def calculate_heterozygosity(self, trait_id: int) -> float:
        """
        Calculate heterozygosity (proportion of heterozygous individuals) for a trait.
        
        Args:
            trait_id: ID of the trait
            
        Returns:
            Heterozygosity value (0.0 to 1.0)
        """
        if not self.creatures:
            return 0.0
        
        heterozygous_count = 0
        total = 0
        
        for creature in self.creatures:
            if trait_id >= len(creature.genome) or creature.genome[trait_id] is None:
                continue
            
            genotype_str = creature.genome[trait_id]
            total += 1
            
            # Check if heterozygous
            # For simple genotypes, check if alleles differ
            if '_' not in genotype_str:
                if len(genotype_str) == 2:
                    if genotype_str[0] != genotype_str[1]:
                        heterozygous_count += 1
                else:
                    # Multi-character: check if halves differ
                    mid = len(genotype_str) // 2
                    if genotype_str[:mid] != genotype_str[mid:]:
                        heterozygous_count += 1
            else:
                # Polygenic: check if any gene pair is heterozygous
                gene_pairs = genotype_str.split('_')
                for pair in gene_pairs:
                    if len(pair) >= 2:
                        mid = len(pair) // 2
                        if pair[:mid] != pair[mid:]:
                            heterozygous_count += 1
                            break
        
        if total == 0:
            return 0.0
        
        return heterozygous_count / total
    
    def calculate_genotype_diversity(self, trait_id: int) -> int:
        """
        Calculate genotype diversity (number of distinct genotypes) for a trait.
        
        Args:
            trait_id: ID of the trait
            
        Returns:
            Number of distinct genotypes present
        """
        if not self.creatures:
            return 0
        
        distinct_genotypes = set()
        
        for creature in self.creatures:
            if trait_id < len(creature.genome) and creature.genome[trait_id] is not None:
                distinct_genotypes.add(creature.genome[trait_id])
        
        return len(distinct_genotypes)
    
    def _persist_creatures(self, db_conn, simulation_id: int, creatures: List[Creature]) -> None:
        """
        Persist creatures to database immediately upon creation.
        
        This method is called for all creatures (founders and offspring) immediately
        when they are created to ensure they have IDs from the start.
        
        Args:
            db_conn: Database connection
            simulation_id: Simulation ID
            creatures: List of creatures to persist (must not already be persisted)
        """
        import sqlite3
        
        cursor = db_conn.cursor()
        
        # Create mapping of all creatures (in population and being persisted) to their IDs
        creature_id_map = {}
        for c in self.creatures:
            if c.creature_id is not None:
                creature_id_map[id(c)] = c.creature_id
        
        # First pass: Persist any parents that are in the population but not yet persisted
        # and are needed by creatures being persisted
        parents_to_persist = set()
        for creature in creatures:
            if creature.birth_cycle > 0:  # Offspring
                # Find parents in population
                for parent in self.creatures:
                    if parent.creature_id is None and parent not in creatures:
                        # Check if this parent matches (simplified: check by birth_cycle and simulation)
                        # In a full implementation, we'd track parent references explicitly
                        if (creature.parent1_id is None or creature.parent2_id is None):
                            # We'll handle this by updating parent IDs after parents are persisted
                            pass
        
        # Batch insert creatures
        for creature in creatures:
            parent1_id = creature.parent1_id
            parent2_id = creature.parent2_id
            
            # Ensure parent IDs match birth_cycle/birth_generation:
            # - Founders (birth_cycle = 0) must have NULL parent IDs
            # - Offspring (birth_cycle > 0) must have non-NULL parent IDs
            if creature.birth_cycle == 0:
                # Founders: ensure parent IDs are NULL
                parent1_id = None
                parent2_id = None
            else:
                # Offspring: ensure parent IDs are not NULL
                # If they're None, we can't persist (constraint violation)
                # This should have been handled before calling this method
                if parent1_id is None or parent2_id is None:
                    raise ValueError(
                        f"Cannot persist offspring (birth_cycle={creature.birth_cycle}) "
                        f"with NULL parent IDs. Parent IDs must be set before persistence."
                    )
            
            cursor.execute("""
                INSERT INTO creatures (
                    simulation_id, birth_cycle, sex, parent1_id, parent2_id, breeder_id,
                    inbreeding_coefficient, lifespan, is_alive,
                    conception_cycle, sexual_maturity_cycle, max_fertility_age_cycle,
                    gestation_end_cycle, nursing_end_cycle, generation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                simulation_id,
                creature.birth_cycle,
                creature.sex,
                parent1_id,
                parent2_id,
                creature.breeder_id,
                creature.inbreeding_coefficient,
                creature.lifespan,
                creature.is_alive,
                creature.conception_cycle,
                creature.sexual_maturity_cycle,
                creature.max_fertility_age_cycle,
                creature.gestation_end_cycle,
                creature.nursing_end_cycle,
                creature.generation
            ))
            creature_id = cursor.lastrowid
            creature.creature_id = creature_id
            
            # Update creature_id_map for future parent lookups
            creature_id_map[id(creature)] = creature_id
            
            # Insert genotypes
            for trait_id, genotype in enumerate(creature.genome):
                if genotype is not None:
                    cursor.execute("""
                        INSERT INTO creature_genotypes (creature_id, trait_id, genotype)
                        VALUES (?, ?, ?)
                    """, (creature_id, trait_id, genotype))
        
        db_conn.commit()

