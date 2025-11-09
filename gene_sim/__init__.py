"""
Genealogical Simulation System

Main API:
    Simulation - Main simulation class
    SimulationResults - Simulation results dataclass
    load_config - Configuration loading helper
"""

from .simulation import Simulation, SimulationResults
from .config import load_config

__all__ = ['Simulation', 'SimulationResults', 'load_config']
__version__ = '0.1.0'

