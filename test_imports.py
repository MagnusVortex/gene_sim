"""Simple script to verify all imports work correctly."""

import sys

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from gene_sim import Simulation, SimulationResults, load_config
        print("✓ Main API imports")
    except Exception as e:
        print(f"✗ Main API imports failed: {e}")
        return False
    
    try:
        from gene_sim.models import Trait, Creature, Population, Generation
        print("✓ Model imports")
    except Exception as e:
        print(f"✗ Model imports failed: {e}")
        return False
    
    try:
        from gene_sim.models.breeder import RandomBreeder, InbreedingAvoidanceBreeder
        print("✓ Breeder imports")
    except Exception as e:
        print(f"✗ Breeder imports failed: {e}")
        return False
    
    try:
        from gene_sim.database import create_database
        print("✓ Database imports")
    except Exception as e:
        print(f"✗ Database imports failed: {e}")
        return False
    
    try:
        from gene_sim.exceptions import ConfigurationError, SimulationError
        print("✓ Exception imports")
    except Exception as e:
        print(f"✗ Exception imports failed: {e}")
        return False
    
    print("\nAll imports successful!")
    return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)

