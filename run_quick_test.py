"""Quick test script to run a simulation."""

from gene_sim import Simulation
import sqlite3

print("=" * 60)
print("Running Quick Simulation Test")
print("=" * 60)
print("\nConfiguration:")
print("  - Initial population: 100 creatures")
print("  - Generations: 20")
print("  - Traits: 5 (all Simple Mendelian)")
print("  - Breeders: 20 random breeders")
print()

# Run simulation
sim = Simulation.from_config('quick_test_config.yaml')
print(f"Database will be created at: {sim.db_path}")
print("\nRunning simulation...\n")

results = sim.run()

print("=" * 60)
print("Simulation Complete!")
print("=" * 60)
print(f"\nResults:")
print(f"  Simulation ID: {results.simulation_id}")
print(f"  Status: {results.status}")
print(f"  Generations completed: {results.generations_completed}")
print(f"  Final population size: {results.final_population_size}")
print(f"  Duration: {results.duration_seconds:.2f} seconds")
print(f"  Database: {results.database_path}")
print()

# Query some statistics
conn = sqlite3.connect(results.database_path)

# Population size over time
print("Population Size Over Generations:")
print("-" * 60)
cursor = conn.cursor()
cursor.execute("""
    SELECT generation, population_size, births, deaths, eligible_males, eligible_females
    FROM generation_stats
    WHERE simulation_id = ?
    ORDER BY generation
""", (results.simulation_id,))
print(f"{'Gen':<6} {'Pop Size':<10} {'Births':<8} {'Deaths':<8} {'Males':<8} {'Females':<8}")
print("-" * 60)
for row in cursor.fetchall():
    gen, pop, births, deaths, males, females = row
    print(f"{gen:<6} {pop:<10} {births:<8} {deaths:<8} {males:<8} {females:<8}")
print()

# Genotype frequencies for trait 0 (Coat Color) - show first and last generations
print("Trait 0 (Coat Color) - Genotype Frequencies:")
print("-" * 60)
cursor.execute("""
    SELECT generation, genotype, frequency
    FROM generation_genotype_frequencies
    WHERE simulation_id = ? AND trait_id = 0
    ORDER BY generation, genotype
""", (results.simulation_id,))
print(f"{'Gen':<6} {'Genotype':<12} {'Frequency':<12}")
print("-" * 60)
for row in cursor.fetchall():
    gen, genotype, freq = row
    print(f"{gen:<6} {genotype:<12} {freq:<12.4f}")
print()

# Final generation statistics for all traits
print("Final Generation (Gen {}) - Genotype Frequencies:".format(results.generations_completed - 1))
print("-" * 60)
final_gen = results.generations_completed - 1
cursor.execute("""
    SELECT trait_id, genotype, frequency
    FROM generation_genotype_frequencies
    WHERE simulation_id = ? AND generation = ?
    ORDER BY trait_id, frequency DESC
""", (results.simulation_id, final_gen))
print(f"{'Trait':<8} {'Genotype':<12} {'Frequency':<12}")
print("-" * 60)
for row in cursor.fetchall():
    trait_id, genotype, freq = row
    print(f"{trait_id:<8} {genotype:<12} {freq:<12.4f}")
print()

conn.close()

print("=" * 60)
print("Done! Check the database for more detailed analysis.")
print("=" * 60)

