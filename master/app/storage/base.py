"""Interfaz de almacenamiento del historial.

Hoy la implementa SQLite local (sqlite.py). Un servicio Cloud futuro (servidor Linux con base de datos) implementaría
esta misma interfaz y se entregaría al Coordinador, sin tocar el reparto de tareas ni el procesamiento.
"""
from typing import Dict, List, Protocol


class Storage(Protocol):
    def guardar_ejecucion(self, ejecucion: Dict) -> int: ...

    def listar_ejecuciones(self, limite: int = 100) -> List[Dict]: ...
