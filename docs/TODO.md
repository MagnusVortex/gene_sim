# Pre-Implementation TODO List

**Last Updated:** November 8, 2025  
**Status:** Design Phase - Before Implementation

---

## Missing Design Elements

### 1. **API/CLI Interface Specification**
   - How users interact with the system
   - CLI commands (e.g., `gene_sim run config.yaml`)
   - Python API structure
   - Entry points and main functions
   - **Location:** New document or add to requirements.md

### 4. **Detailed Reporting/Visualization Specs**
   - Report structure and format
   - Chart types and data sources
   - Export formats (CSV/JSON structure)
   - Report file organization
   - **Location:** [Simulation Model](models/simulation.md) section 9

### 5. **Configuration Loading & Validation Details**
   - YAML parsing and transformation
   - Validation rules and error messages
   - Default values and normalization
   - Configuration object structure
   - **Location:** [Simulation Model](models/simulation.md) section 4

### 6. **Algorithm Specifications**
   - Inbreeding coefficient calculation (mentioned in Breeder model)
   - Gamete formation details (mentioned but could be more specific)
   - Allele frequency calculation from genotypes
   - Heterozygosity calculation
   - **Locations:** 
     - Inbreeding: [Breeder Model](models/breeder.md)
     - Gamete formation: [Creature Model](models/creature.md) section 5
     - Allele/Heterozygosity: [Population Model](models/population.md) or new section

### 7. **Error Handling Strategy**
   - Error types and handling approach
   - Validation error messages
   - Database error handling
   - Graceful degradation
   - **Location:** [Simulation Model](models/simulation.md) section 11

---

## Next Steps

1. Complete missing design elements above
2. Review all models for completeness
3. Create implementation plan
4. Begin test-driven implementation

---

**Note:** This list should be updated as items are completed or new requirements are identified.

