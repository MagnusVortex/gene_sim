"""Create charts tracking phenotype percentages throughout the simulation."""

import sqlite3
import glob
import matplotlib.pyplot as plt
from collections import defaultdict

def get_latest_db():
    """Get the most recent simulation database file."""
    import os
    from pathlib import Path
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

def get_phenotype_frequencies(conn, simulation_id, trait_id):
    """Get phenotype frequencies for each cycle for a specific trait."""
    cursor = conn.cursor()
    
    # Get all cycles
    cursor.execute("""
        SELECT DISTINCT generation
        FROM generation_stats
        WHERE simulation_id = ?
        ORDER BY generation
    """, (simulation_id,))
    cycles = [row[0] for row in cursor.fetchall()]
    
    # Get genotype frequencies for all cycles
    cursor.execute("""
        SELECT ggf.generation, ggf.genotype, ggf.frequency
        FROM generation_genotype_frequencies ggf
        WHERE ggf.simulation_id = ? AND ggf.trait_id = ?
        ORDER BY ggf.generation, ggf.genotype
    """, (simulation_id, trait_id))
    
    # Aggregate by phenotype
    phenotype_data = defaultdict(lambda: defaultdict(float))  # phenotype -> cycle -> frequency
    
    for cycle, genotype, frequency in cursor.fetchall():
        # Get phenotype for this genotype
        cursor.execute("""
            SELECT phenotype
            FROM genotypes
            WHERE trait_id = ? AND genotype = ?
        """, (trait_id, genotype))
        result = cursor.fetchone()
        if result:
            phenotype = result[0]
            phenotype_data[phenotype][cycle] += frequency
    
    return cycles, dict(phenotype_data)

def chart_phenotype(db_path, trait_id=None, phenotype_name=None):
    """Create a chart tracking phenotype percentages over cycles."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get simulation ID
    cursor.execute("SELECT simulation_id FROM simulations ORDER BY simulation_id DESC LIMIT 1")
    simulation_id = cursor.fetchone()[0]
    
    # Get trait information
    trait_info = get_trait_info(conn)
    
    # If no trait specified, show all traits
    if trait_id is None:
        trait_ids = sorted(trait_info.keys())
    else:
        if trait_id not in trait_info:
            print(f"Error: Trait {trait_id} not found!")
            conn.close()
            return
        trait_ids = [trait_id]
    
    # Create subplots for each trait
    num_traits = len(trait_ids)
    fig, axes = plt.subplots(num_traits, 1, figsize=(14, 5 * num_traits))
    if num_traits == 1:
        axes = [axes]
    
    for idx, tid in enumerate(trait_ids):
        ax = axes[idx]
        trait_name = trait_info[tid]['name']
        
        # Get phenotype frequencies
        cycles, phenotype_data = get_phenotype_frequencies(conn, simulation_id, tid)
        
        # Plot each phenotype
        plotted_any = False
        for phenotype in sorted(phenotype_data.keys()):
            # Only plot the requested phenotype if specified
            if phenotype_name is None or phenotype == phenotype_name:
                frequencies = [phenotype_data[phenotype].get(cycle, 0) * 100 for cycle in cycles]
                ax.plot(cycles, frequencies, marker='o', label=phenotype, linewidth=2.5, markersize=4, alpha=0.8)
                plotted_any = True
        
        if not plotted_any:
            print(f"Warning: Phenotype '{phenotype_name}' not found for trait {tid}")
            continue
        
        ax.set_xlabel('Cycle', fontsize=13, fontweight='bold')
        ax.set_ylabel('Percentage (%)', fontsize=13, fontweight='bold')
        if phenotype_name:
            title = f'Trait {tid}: {trait_name} - {phenotype_name} Frequency Over Time'
        else:
            title = f'Trait {tid}: {trait_name} - Phenotype Frequencies Over Time'
        ax.set_title(title, fontsize=15, fontweight='bold', pad=15)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='best', fontsize=11, framealpha=0.9)
        ax.set_ylim([0, 100])
        ax.set_xlim([min(cycles), max(cycles)])
        
        # Add some styling
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    
    # Save the chart
    if phenotype_name:
        output_file = f'phenotype_{phenotype_name.lower().replace(" ", "_")}_frequencies.png'
    else:
        output_file = 'phenotype_frequencies.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nChart saved to: {output_file}")
    
    # Also display it
    try:
        plt.show()
    except:
        print("(Chart display not available in this environment)")
    
    conn.close()

def list_available_phenotypes(db_path):
    """List all available traits and phenotypes."""
    conn = sqlite3.connect(db_path)
    trait_info = get_trait_info(conn)
    
    print("\nAvailable Traits and Phenotypes:")
    print("=" * 60)
    for trait_id in sorted(trait_info.keys()):
        trait_name = trait_info[trait_id]['name']
        phenotypes = set(trait_info[trait_id]['genotypes'].values())
        print(f"\nTrait {trait_id}: {trait_name}")
        for phenotype in sorted(phenotypes):
            print(f"  - {phenotype}")
    
    conn.close()

if __name__ == '__main__':
    import sys
    
    db_path = get_latest_db()
    if not db_path:
        print("No simulation database found!")
        sys.exit(1)
    
    print(f"Analyzing database: {db_path}")
    
    # List available options
    list_available_phenotypes(db_path)
    
    # If arguments provided, chart specific trait/phenotype
    if len(sys.argv) > 1:
        trait_id = int(sys.argv[1]) if sys.argv[1].isdigit() else None
        phenotype_name = sys.argv[2] if len(sys.argv) > 2 else None
        chart_phenotype(db_path, trait_id, phenotype_name)
    else:
        # Default: chart all phenotypes for all traits
        print("\nCreating charts for all traits and phenotypes...")
        print("Usage: python chart_phenotype.py [trait_id] [phenotype_name]")
        print("Example: python chart_phenotype.py 0 Black")
        print()
        chart_phenotype(db_path)

