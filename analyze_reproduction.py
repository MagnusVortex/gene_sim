"""Analyze reproduction rates from simulation database."""

import sqlite3
import sys

if len(sys.argv) < 2:
    print("Usage: python analyze_reproduction.py <database_path>")
    sys.exit(1)

db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 80)
print("Reproduction Analysis")
print("=" * 80)
print()

# Get generation statistics
cursor.execute("""
    SELECT generation, population_size, eligible_males, eligible_females, births
    FROM generation_stats
    ORDER BY generation
""")

print(f"{'Gen':<6} {'Eligible':<12} {'Eligible':<12} {'Births':<10} {'% Males':<12} {'% Females':<12} {'% Total':<12}")
print(f"{'':<6} {'Males':<12} {'Females':<12} {'':<10} {'Reproduced':<12} {'Reproduced':<12} {'Reproduced':<12}")
print("-" * 80)

for row in cursor.fetchall():
    gen, pop_size, eligible_males, eligible_females, births = row
    
    # Calculate percentages
    # Each birth requires one male and one female
    # So the number of unique males/females that reproduced is at most equal to births
    # (assuming each pair produces one offspring, which they do)
    males_reproduced = min(births, eligible_males) if eligible_males > 0 else 0
    females_reproduced = min(births, eligible_females) if eligible_females > 0 else 0
    
    pct_males = (males_reproduced / eligible_males * 100) if eligible_males > 0 else 0.0
    pct_females = (females_reproduced / eligible_females * 100) if eligible_females > 0 else 0.0
    
    total_eligible = eligible_males + eligible_females
    total_reproduced = males_reproduced + females_reproduced
    pct_total = (total_reproduced / total_eligible * 100) if total_eligible > 0 else 0.0
    
    print(f"{gen:<6} {eligible_males:<12} {eligible_females:<12} {births:<10} "
          f"{pct_males:<12.2f} {pct_females:<12.2f} {pct_total:<12.2f}")

print("-" * 80)

# Summary statistics
cursor.execute("""
    SELECT 
        AVG(eligible_males) as avg_eligible_males,
        AVG(eligible_females) as avg_eligible_females,
        AVG(births) as avg_births,
        SUM(births) as total_births
    FROM generation_stats
""")
row = cursor.fetchone()
avg_males, avg_females, avg_births, total_births = row

print("\nSummary Statistics:")
print(f"  Average eligible males per generation: {avg_males:.1f}")
print(f"  Average eligible females per generation: {avg_females:.1f}")
print(f"  Average births per generation: {avg_births:.1f}")
print(f"  Total births across all generations: {total_births}")
print()

# Calculate overall reproduction rates
avg_pct_males = (avg_births / avg_males * 100) if avg_males > 0 else 0.0
avg_pct_females = (avg_births / avg_females * 100) if avg_females > 0 else 0.0
avg_total_eligible = avg_males + avg_females
avg_pct_total = ((avg_births * 2) / avg_total_eligible * 100) if avg_total_eligible > 0 else 0.0

print("Average Reproduction Rates:")
print(f"  Average % of eligible males that reproduced: {avg_pct_males:.2f}%")
print(f"  Average % of eligible females that reproduced: {avg_pct_females:.2f}%")
print(f"  Average % of total eligible creatures that reproduced: {avg_pct_total:.2f}%")
print()

conn.close()

