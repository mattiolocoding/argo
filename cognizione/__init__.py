"""
ARGO - cognizione
Nucleo isolato per osservazione, timeline e inferenza semplice.

API principale:
    from cognizione import TimelineCognitiva
"""

from .timeline import (
    TIPI_EVENTO,
    EventoCognitivo,
    TimelineCognitiva,
    normalizza_evento,
)
from .world_model import WorldModel
from .diario_interno import DiarioInterno
from .obiettivi import Obiettivi
from .esperimenti import EsperimentiCognitivi

__all__ = [
    "DiarioInterno",
    "EsperimentiCognitivi",
    "Obiettivi",
    "TIPI_EVENTO",
    "EventoCognitivo",
    "TimelineCognitiva",
    "WorldModel",
    "normalizza_evento",
]
