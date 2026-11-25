"""Cola de tareas de una sesión de procesamiento.

Estados de una tarea: pendiente → asignada → completada. Si el worker se cae, asignada → pendiente.
Un resultado se acepta una sola vez por tarea (idempotencia), llegue de quien llegue.
"""
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

from ..fasta.bloques import iterar_bloques
from ..fasta.conteo import sumar

VACIO = {"A": 0, "T": 0, "C": 0, "G": 0, "otros": 0}
CLAVES = tuple(VACIO)


@dataclass
class Tarea:
    id: str
    indice: int
    offset: int
    longitud: int
    estado: str = "pendiente"          # pendiente | asignada | completada
    worker_id: Optional[str] = None
    intentos: int = 0
    asignada_en: float = 0.0
    completada_por: Optional[str] = None


class Cola:
    def __init__(self, sesion_id: str, ruta: str, tamano_bloque: int):
        self.sesion_id, self.ruta, self.tamano_bloque = sesion_id, ruta, tamano_bloque
        self.tareas: Dict[str, Tarea] = {}
        self.pendientes: Deque[str] = deque()
        for b in iterar_bloques(ruta, tamano_bloque):
            t = Tarea(id=f"{sesion_id}-{b.indice:06d}", indice=b.indice, offset=b.offset, longitud=b.longitud)
            self.tareas[t.id] = t
            self.pendientes.append(t.id)
        self.conteo: Dict[str, int] = dict(VACIO)
        self.bytes_completados = 0
        self.duplicados_rechazados = 0

    # --- asignación -------------------------------------------------------------------------------------------
    def asignar(self, worker_id: str, ahora: float) -> Optional[Tarea]:
        if not self.pendientes:
            return None
        t = self.tareas[self.pendientes.popleft()]
        t.estado, t.worker_id, t.asignada_en = "asignada", worker_id, ahora
        t.intentos += 1
        return t

    def liberar_de(self, worker_id: str) -> List[str]:
        """Devuelve a la cola las tareas que tenía ese worker; van al frente para terminar pronto."""
        liberadas = [t.id for t in self.tareas.values() if t.estado == "asignada" and t.worker_id == worker_id]
        for tid in sorted(liberadas, reverse=True):
            t = self.tareas[tid]
            t.estado, t.worker_id = "pendiente", None
            self.pendientes.appendleft(tid)
        return liberadas

    # --- resultados -------------------------------------------------------------------------------------------
    def completar(self, task_id: str, worker_id: str, conteo: dict, n_bytes: int) -> Tuple[bool, str]:
        t = self.tareas.get(task_id)
        if t is None:
            return False, "tarea_desconocida"
        if t.estado == "completada":
            self.duplicados_rechazados += 1
            return False, "duplicado"
        motivo = self._invalido(t, conteo, n_bytes)
        if motivo:
            return False, motivo
        if t.estado == "pendiente":                       # llegó tarde, tras ser reasignada y antes de reasignarse otra vez
            self.pendientes.remove(t.id)
        t.estado, t.completada_por = "completada", worker_id
        self.conteo = sumar(self.conteo, conteo)
        self.bytes_completados += t.longitud
        return True, "ok"

    @staticmethod
    def _invalido(t: Tarea, conteo, n_bytes) -> Optional[str]:
        if not isinstance(conteo, dict) or set(conteo) != set(CLAVES):
            return "conteo_mal_formado"
        if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in conteo.values()):
            return "conteo_mal_formado"
        if n_bytes != t.longitud:
            return "bytes_no_coinciden"
        if sum(conteo.values()) > t.longitud:
            return "conteo_excede_bloque"
        return None

    # --- estado -----------------------------------------------------------------------------------------------
    def resumen(self) -> Dict[str, int]:
        c = {"pendiente": 0, "asignada": 0, "completada": 0}
        for t in self.tareas.values():
            c[t.estado] += 1
        return c

    @property
    def terminada(self) -> bool:
        return all(t.estado == "completada" for t in self.tareas.values())

    @property
    def bytes_totales(self) -> int:
        return sum(t.longitud for t in self.tareas.values())
