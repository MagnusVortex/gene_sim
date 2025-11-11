"""Analyze genotype frequencies per cycle from simulation database."""

import sqlite3
import glob
import json
from pathlib import Path

def get_latest_db():
    """Get the most recent simulation database file."""
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

def analyze_genotype_frequencies(db_path):
    """Analyze and display genotype frequencies per cycle."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get simulation ID
    cursor.execute("SELECT simulation_id FROM simulations ORDER BY simulation_id DESC LIMIT 1")
    simulation_id = cursor.fetchone()[0]
    
    # Get trait information
    trait_info = get_trait_info(conn)
    
    # Get all cycles - show first few, middle, and last cycles
    cursor.execute("""
        SELECT COUNT(DISTINCT generation)
        FROM generation_stats
        WHERE simulation_id = ?
    """, (simulation_id,))
    total_cycles = cursor.fetchone()[0]
    
    # Get first 3, middle 2, and last 3 cycles
    cycles_to_show = [0, 1, 2]  # First 3
    if total_cycles > 6:
        mid_point = total_cycles // 2
        cycles_to_show.extend([mid_point - 1, mid_point])  # Middle 2
    if total_cycles > 3:
        cycles_to_show.extend([total_cycles - 3, total_cycles - 2, total_cycles - 1])  # Last 3
    
    cycles_to_show = sorted(set(cycles_to_show))  # Remove duplicates and sort
    
    print(f"Showing cycles: {cycles_to_show} (out of {total_cycles} total cycles)\n")
    
    # Get genotype frequencies for each cycle
    for cycle in cycles_to_show:
        print(f"\n{'='*80}")
        print(f"CYCLE {cycle}")
        print(f"{'='*80}")
        
        # Get genotype frequencies for this cycle
        cursor.execute("""
            SELECT ggf.trait_id, ggf.genotype, ggf.frequency
            FROM generation_genotype_frequencies ggf
            WHERE ggf.simulation_id = ? AND ggf.generation = ?
            ORDER BY ggf.trait_id, ggf.genotype
        """, (simulation_id, cycle))
        
        current_trait_id = None
        genotype_data = []
        for trait_id, genotype, frequency in cursor.fetchall():
            if trait_id not in trait_info:
                continue  # Skip if trait info not found
            
            phenotype = trait_info[trait_id]['genotypes'].get(genotype, 'Unknown')
            genotype_data.append((trait_id, genotype, phenotype, frequency))
        
        # Group by trait and sort by phenotype within each trait
        trait_groups = {}
        for trait_id, genotype, phenotype, frequency in genotype_data:
            if trait_id not in trait_groups:
                trait_groups[trait_id] = []
            trait_groups[trait_id].append((genotype, phenotype, frequency))
        
        # Sort traits and within each trait, sort by phenotype then genotype
        for trait_id in sorted(trait_groups.keys()):
            trait_name = trait_info[trait_id]['name']
            print(f"\nTrait {trait_id}: {trait_name}")
            print("-" * 80)
            
            # Sort by phenotype first, then genotype
            sorted_genotypes = sorted(trait_groups[trait_id], key=lambda x: (x[1], x[0]))
            for genotype, phenotype, frequency in sorted_genotypes:
                percentage = frequency * 100
                print(f"  {genotype:10} ({phenotype:15}): {percentage:6.2f}%")
    
    conn.close()

if __name__ == '__main__':
    db_path = get_latest_db()
    if db_path:
        print(f"Analyzing database: {db_path}")
        analyze_genotype_frequencies(db_path)
    else:
        print("No simulation database found!")

