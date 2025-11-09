"""Custom exceptions for the gene_sim package."""


class GeneSimError(Exception):
    """Base exception for gene_sim package."""
    pass


class ConfigurationError(GeneSimError):
    """Configuration validation or loading error."""
    pass


class SimulationError(GeneSimError):
    """Simulation execution error."""
    pass


class DatabaseError(GeneSimError):
    """Database operation error."""
    pass

