"""Analyze genotype frequencies by cycle from simulation database."""

import sqlite3
import sys
import glob
from pathlib import Path

def analyze_genotype_frequencies(db_path: str):
    """Show genotype frequencies for each cycle, ordered by trait and phenotype."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get simulation ID (assuming single simulation per database)
    cursor.execute("SELECT simulation_id FROM simulations LIMIT 1")
    sim_result = cursor.fetchone()
    if not sim_result:
        print("No simulation found in database")
        return
    simulation_id = sim_result[0]
    
    # Get trait names (traits table doesn't have simulation_id)
    cursor.execute("""
        SELECT trait_id, name 
        FROM traits 
        ORDER BY trait_id
    """)
    traits = {trait_id: name for trait_id, name in cursor.fetchall()}
    
    # Get genotype to phenotype mapping (genotypes table doesn't have simulation_id)
    cursor.execute("""
        SELECT trait_id, genotype, phenotype
        FROM genotypes
        ORDER BY trait_id, phenotype, genotype
    """)
    genotype_to_phenotype = {}
    for trait_id, genotype, phenotype in cursor.fetchall():
        if trait_id not in genotype_to_phenotype:
            genotype_to_phenotype[trait_id] = {}
        genotype_to_phenotype[trait_id][genotype] = phenotype
    
    # Get all cycles
    cursor.execute("""
        SELECT DISTINCT generation 
        FROM generation_stats 
        WHERE simulation_id = ?
        ORDER BY generation
    """, (simulation_id,))
    cycles = [row[0] for row in cursor.fetchall()]
    
    # For each cycle, get genotype frequencies
    for cycle in cycles:
        print(f"\n{'='*80}")
        print(f"Cycle {cycle}")
        print(f"{'='*80}")
        
        # Get genotype frequencies for this cycle
        cursor.execute("""
            SELECT ggf.trait_id, ggf.genotype, ggf.frequency
            FROM generation_genotype_frequencies ggf
            WHERE ggf.simulation_id = ? AND ggf.generation = ?
            ORDER BY ggf.trait_id, ggf.genotype
        """, (simulation_id, cycle))
        
        current_trait = None
        current_phenotype = None
        
        for trait_id, genotype, frequency in cursor.fetchall():
            phenotype = genotype_to_phenotype.get(trait_id, {}).get(genotype, "Unknown")
            percentage = frequency * 100
            
            # Print trait header if new trait
            if trait_id != current_trait:
                if current_trait is not None:
                    print()  # Blank line between traits
                trait_name = traits.get(trait_id, f"Trait {trait_id}")
                print(f"\n{trait_name} (Trait ID: {trait_id})")
                print("-" * 80)
                current_trait = trait_id
                current_phenotype = None
            
            # Print phenotype header if new phenotype
            if phenotype != current_phenotype:
                if current_phenotype is not None:
                    print()  # Blank line between phenotypes
                print(f"  {phenotype}:")
                current_phenotype = phenotype
            
            # Print genotype frequency
            print(f"    {genotype:10} : {percentage:6.2f}%")
        
        print()  # Blank line after cycle
    
    conn.close()

if __name__ == "__main__":
    # Find the most recent database file
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_pattern = os.path.join(parent_dir, 'simulation_*.db')
    db_files = sorted(glob.glob(db_pattern), key=lambda x: Path(x).stat().st_mtime, reverse=True)
    
    if not db_files:
        print("No simulation database files found")
        sys.exit(1)
    
    db_path = db_files[0]
    print(f"Analyzing database: {db_path}\n")
    
    analyze_genotype_frequencies(db_path)

