"""Comprehensive analytics showing population and breeding pool statistics."""

import sqlite3
import glob
from pathlib import Path


def get_latest_db():
    """Get the most recent simulation database file."""
    # Look in parent directory (gene_sim root)
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_pattern = os.path.join(parent_dir, 'simulation_*.db')
    db_files = sorted(glob.glob(db_pattern), key=lambda x: Path(x).stat().st_mtime, reverse=True)
    return db_files[0] if db_files else None


def get_trait_info(conn):
    """Get trait information including genotype to phenotype mapping."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.trait_id, t.name, g.genotype, g.phenotype
        FROM traits t
        JOIN genotypes g ON t.trait_id = g.trait_id
        ORDER BY t.trait_id, g.genotype
    """)
    
    trait_info = {}
    for trait_id, trait_name, genotype, phenotype in cursor.fetchall():
        if trait_id not in trait_info:
            trait_info[trait_id] = {
                'name': trait_name,
                'genotypes': {}
            }
        trait_info[trait_id]['genotypes'][genotype] = phenotype
    
    return trait_info


def calculate_breeding_eligible_creatures(conn, simulation_id, cycle):
    """
    Calculate which creatures were eligible for breeding at a given cycle.
    
    This approximates breeding eligibility using database fields:
    - Must be alive (based on birth_cycle and lifespan)
    - Must have reached sexual maturity
    - Must not be past max fertility age
    - Females must not be gestating or nursing
    """
    cursor = conn.cursor()
    
    # Get all alive creatures at this cycle
    # A creature is alive at cycle N if:
    # - birth_cycle <= cycle (creature was born by this cycle)
    # - is_alive = 1 (creature is marked as alive)
    cursor.execute("""
        SELECT creature_id, sex, birth_cycle, sexual_maturity_cycle, 
               max_fertility_age_cycle, gestation_end_cycle, nursing_end_cycle
        FROM creatures
        WHERE simulation_id = ? 
          AND birth_cycle <= ?
          AND is_alive = 1
    """, (simulation_id, cycle))
    
    eligible_creature_ids = []
    for row in cursor.fetchall():
        creature_id, sex, birth_cycle, sexual_maturity_cycle, max_fertility_age_cycle, \
        gestation_end_cycle, nursing_end_cycle = row
        
        # Check sexual maturity
        if sexual_maturity_cycle is not None and cycle < sexual_maturity_cycle:
            continue
        
        # Check max fertility age
        if max_fertility_age_cycle is not None and cycle >= max_fertility_age_cycle:
            continue
        
        # For females, check gestation and nursing
        if sex == 'female':
            if gestation_end_cycle is not None and cycle < gestation_end_cycle:
                continue
            if nursing_end_cycle is not None and cycle < nursing_end_cycle:
                continue
        
        eligible_creature_ids.append(creature_id)
    
    return eligible_creature_ids


def calculate_genotype_frequencies_for_creatures(conn, creature_ids, trait_id):
    """Calculate genotype frequencies for a specific set of creatures."""
    if not creature_ids:
        return {}
    
    cursor = conn.cursor()
    placeholders = ','.join(['?'] * len(creature_ids))
    
    cursor.execute(f"""
        SELECT genotype, COUNT(*) as count
        FROM creature_genotypes
        WHERE creature_id IN ({placeholders}) AND trait_id = ?
        GROUP BY genotype
    """, creature_ids + [trait_id])
    
    counts = {row[0]: row[1] for row in cursor.fetchall()}
    total = sum(counts.values())
    
    if total == 0:
        return {}
    
    return {genotype: count / total for genotype, count in counts.items()}


def calculate_total_population_alive(conn, simulation_id, cycle):
    """Calculate total population alive at a given cycle."""
    cursor = conn.cursor()
    # A creature is alive at cycle N if:
    # - birth_cycle <= cycle (creature was born by this cycle)
    # - is_alive = 1 (creature is marked as alive in database)
    # Note: We use is_alive flag since lifespan storage may have issues
    cursor.execute("""
        SELECT COUNT(*)
        FROM creatures
        WHERE simulation_id = ? 
          AND birth_cycle <= ?
          AND is_alive = 1
    """, (simulation_id, cycle))
    
    result = cursor.fetchone()
    return result[0] if result else 0


def analyze_comprehensive(db_path):
    """Analyze and display comprehensive population and breeding statistics."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get simulation ID
    cursor.execute("SELECT simulation_id FROM simulations ORDER BY simulation_id DESC LIMIT 1")
    result = cursor.fetchone()
    if not result:
        print("No simulation found in database")
        conn.close()
        return
    
    simulation_id = result[0]
    
    # Get trait information
    trait_info = get_trait_info(conn)
    
    # Get all cycles
    cursor.execute("""
        SELECT DISTINCT generation
        FROM generation_stats
        WHERE simulation_id = ?
        ORDER BY generation
    """, (simulation_id,))
    cycles = [row[0] for row in cursor.fetchall()]
    
    if not cycles:
        print("No cycle data found")
        conn.close()
        return
    
    # Show first few, middle, and last cycles
    total_cycles = len(cycles)
    cycles_to_show = [0, 1, 2]  # First 3
    if total_cycles > 6:
        mid_point = total_cycles // 2
        cycles_to_show.extend([mid_point - 1, mid_point])  # Middle 2
    if total_cycles > 3:
        cycles_to_show.extend([total_cycles - 3, total_cycles - 2, total_cycles - 1])  # Last 3
    
    cycles_to_show = sorted(set(cycles_to_show))
    
    print(f"\n{'='*100}")
    print(f"COMPREHENSIVE POPULATION ANALYTICS")
    print(f"{'='*100}")
    print(f"Database: {db_path}")
    print(f"Showing cycles: {cycles_to_show} (out of {total_cycles} total cycles)\n")
    
    for cycle in cycles_to_show:
        print(f"\n{'='*100}")
        print(f"CYCLE {cycle}")
        print(f"{'='*100}")
        
        # Get generation stats
        cursor.execute("""
            SELECT population_size, eligible_males, eligible_females
            FROM generation_stats
            WHERE simulation_id = ? AND generation = ?
        """, (simulation_id, cycle))
        
        gen_stats = cursor.fetchone()
        if not gen_stats:
            print(f"No stats found for cycle {cycle}")
            continue
        
        stored_pop_size, eligible_males, eligible_females = gen_stats
        total_breeding = eligible_males + eligible_females
        
        # Use population_size from stats (this is the working pool size at that cycle)
        total_pop_alive = stored_pop_size
        
        # Get breeding eligible creature IDs - use stored eligible counts and query creatures
        # For historical cycles, we need to find creatures that were alive AND eligible
        # Since is_alive only reflects current state, we'll use the stored genotype frequencies
        # for total population and calculate breeding pool from eligible creatures
        
        # Get creatures that were alive at this cycle (born by cycle, and either still alive
        # or died after this cycle - approximate by checking if they could have been alive)
        cursor.execute("""
            SELECT creature_id
            FROM creatures
            WHERE simulation_id = ? 
              AND birth_cycle <= ?
              AND (is_alive = 1 OR birth_cycle <= ?)
        """, (simulation_id, cycle, cycle))
        all_creature_ids_at_cycle = [row[0] for row in cursor.fetchall()]
        
        # For breeding pool, we'll approximate by getting creatures that match eligibility criteria
        # This is an approximation since we can't perfectly reconstruct historical state
        breeding_creature_ids = calculate_breeding_eligible_creatures(conn, simulation_id, cycle)
        
        print(f"\nPOPULATION STATISTICS:")
        print(f"  Total Population Alive: {total_pop_alive}")
        print(f"  Total Breeding Creatures: {total_breeding} ({eligible_males} males, {eligible_females} females)")
        print(f"  Breeding Pool Size (calculated): {len(breeding_creature_ids)}")
        
        # For each trait, show genotype frequencies for both pools
        for trait_id in sorted(trait_info.keys()):
            trait_name = trait_info[trait_id]['name']
            print(f"\n{'-'*100}")
            print(f"Trait {trait_id}: {trait_name}")
            print(f"{'-'*100}")
            
            # Get genotype frequencies for total population alive
            # Use stored frequencies from generation_genotype_frequencies (these are for working pool)
            cursor.execute("""
                SELECT genotype, frequency
                FROM generation_genotype_frequencies
                WHERE simulation_id = ? AND generation = ? AND trait_id = ?
            """, (simulation_id, cycle, trait_id))
            stored_freqs = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Use stored frequencies if available, otherwise calculate from creatures
            if stored_freqs:
                total_pop_freqs = stored_freqs
                # Get creature IDs for count calculation (approximate)
                cursor.execute("""
                    SELECT creature_id
                    FROM creatures
                    WHERE simulation_id = ? 
                      AND birth_cycle <= ?
                      AND (is_alive = 1 OR birth_cycle <= ?)
                """, (simulation_id, cycle, cycle))
                total_pop_creature_ids = [row[0] for row in cursor.fetchall()]
            else:
                # Fallback: calculate from creatures
                cursor.execute("""
                    SELECT creature_id
                    FROM creatures
                    WHERE simulation_id = ? 
                      AND birth_cycle <= ?
                      AND (is_alive = 1 OR birth_cycle <= ?)
                """, (simulation_id, cycle, cycle))
                total_pop_creature_ids = [row[0] for row in cursor.fetchall()]
                total_pop_freqs = calculate_genotype_frequencies_for_creatures(
                    conn, total_pop_creature_ids, trait_id
                )
            
            # Get genotype frequencies for breeding pool
            breeding_freqs = calculate_genotype_frequencies_for_creatures(
                conn, breeding_creature_ids, trait_id
            )
            
            # Display in a table format
            print(f"\n{'Genotype':<15} {'Phenotype':<20} {'Total Pop %':<15} {'Breeding Pool %':<15}")
            print(f"{'-'*65}")
            
            # Get all genotypes for this trait
            all_genotypes = set(total_pop_freqs.keys()) | set(breeding_freqs.keys())
            
            for genotype in sorted(all_genotypes):
                phenotype = trait_info[trait_id]['genotypes'].get(genotype, 'Unknown')
                total_pct = total_pop_freqs.get(genotype, 0) * 100
                breeding_pct = breeding_freqs.get(genotype, 0) * 100
                
                print(f"{genotype:<15} {phenotype:<20} {total_pct:>13.2f}% {breeding_pct:>13.2f}%")
            
            # Show counts if available (batch queries to avoid SQLite variable limit)
            if total_pop_creature_ids:
                # SQLite has a limit of 999 variables, so batch if needed
                batch_size = 900
                total_counts = {}
                for i in range(0, len(total_pop_creature_ids), batch_size):
                    batch_ids = total_pop_creature_ids[i:i+batch_size]
                    placeholders = ','.join(['?'] * len(batch_ids))
                    cursor.execute(f"""
                        SELECT genotype, COUNT(*) as count
                        FROM creature_genotypes
                        WHERE creature_id IN ({placeholders}) 
                          AND trait_id = ?
                        GROUP BY genotype
                    """, batch_ids + [trait_id])
                    for row in cursor.fetchall():
                        genotype, count = row
                        total_counts[genotype] = total_counts.get(genotype, 0) + count
                
                breeding_counts = {}
                if breeding_creature_ids:
                    for i in range(0, len(breeding_creature_ids), batch_size):
                        batch_ids = breeding_creature_ids[i:i+batch_size]
                        placeholders = ','.join(['?'] * len(batch_ids))
                        cursor.execute(f"""
                            SELECT genotype, COUNT(*) as count
                            FROM creature_genotypes
                            WHERE creature_id IN ({placeholders}) 
                              AND trait_id = ?
                            GROUP BY genotype
                        """, batch_ids + [trait_id])
                        for row in cursor.fetchall():
                            genotype, count = row
                            breeding_counts[genotype] = breeding_counts.get(genotype, 0) + count
                
                print(f"\nCounts:")
                for genotype in sorted(all_genotypes):
                    total_count = total_counts.get(genotype, 0)
                    breeding_count = breeding_counts.get(genotype, 0)
                    print(f"  {genotype}: Total Pop = {total_count}, Breeding Pool = {breeding_count}")
        
        print()  # Blank line between cycles
    
    conn.close()


if __name__ == '__main__':
    db_path = get_latest_db()
    if db_path:
        print(f"Analyzing database: {db_path}")
        analyze_comprehensive(db_path)
    else:
        print("No simulation database found!")
        import os
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print(f"Looking for files matching: {os.path.join(parent_dir, 'simulation_*.db')}")

