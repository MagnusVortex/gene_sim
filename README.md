# Genealogical Simulation System

A Python-based simulation system for modeling genetic inheritance, breeding strategies, and population dynamics across multiple generations.

## Features

- **Genetic Modeling**: Supports multiple inheritance patterns (Mendelian, sex-linked, polygenic, etc.)
- **Breeding Strategies**: Multiple breeder types (random, inbreeding avoidance, phenotype selection)
- **Multi-Generational Tracking**: Complete lineage and pedigree tracking
- **SQLite Persistence**: Efficient data storage and querying
- **Reproducible**: Seeded random number generation for deterministic results

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from gene_sim import Simulation

# Run simulation from config file
sim = Simulation.from_config('config.yaml')
results = sim.run()

# Access results
print(f"Simulation ID: {results.simulation_id}")
print(f"Database: {results.database_path}")
```

## Documentation

See `docs/` directory for complete documentation:
- API Interface: `docs/api-interface.md`
- Database Schema: `docs/database-schema.md`
- Domain Models: `docs/domain-model.md`
- Configuration: `docs/config-example.yaml`

## Requirements

- Python 3.10+
- NumPy
- PyYAML

## License

[To be determined]

