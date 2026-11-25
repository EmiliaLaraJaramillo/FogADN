"""Registro de workers (celulares) y su estado visible en el dashboard."""
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional

NO_DISPONIBLE = "No disponible"
ESTADOS = ("disponible", "procesando", "completado", "desconectado", "error")


@dataclass
class Worker:
    id: str
    info: Dict[str, object]
    estado: str = "disponible"
    ultima_comunicacion: float = 0.0
    conectado_desde: float = 0.0
    progreso: float = 0.0                  # 0-100 del bloque en curso
    bloques_procesados: int = 0
    bytes_procesados: int = 0
    t_proceso_ms: float = 0.0
    t_transfer_ms: float = 0.0
    tarea_actual: Optional[str] = None
    errores: int = 0

    def visible(self) -> Dict[str, object]:
        return dict(id=self.id, **self.info, estado=self.estado, progreso=round(self.progreso, 1),
                    bloques_procesados=self.bloques_procesados, bytes_procesados=self.bytes_procesados,
                    t_proceso_ms=round(self.t_proceso_ms), t_transfer_ms=round(self.t_transfer_ms),
                    ultima_comunicacion=self.ultima_comunicacion, tarea_actual=self.tarea_actual,
                    errores=self.errores)


def _texto(v, maximo=120) -> str:
    return str(v)[:maximo] if v not in (None, "", 0) else NO_DISPONIBLE


def limpiar_info(bruta: dict) -> Dict[str, object]:
    """Solo se guarda lo que el navegador informó; lo ausente figura como «No disponible» (nada se inventa)."""
    bruta = bruta or {}
    nucleos = bruta.get("nucleos")
    memoria = bruta.get("memoria_gb")
    return dict(
        modelo=_texto(bruta.get("modelo")),
        plataforma=_texto(bruta.get("plataforma")),
        navegador=_texto(bruta.get("navegador")),
        nucleos=int(nucleos) if isinstance(nucleos, (int, float)) and nucleos > 0 else NO_DISPONIBLE,
        memoria_gb=float(memoria) if isinstance(memoria, (int, float)) and memoria > 0 else NO_DISPONIBLE,
        tipo=_texto(bruta.get("tipo"), 30),
        pantalla=_texto(bruta.get("pantalla"), 40),
        gpu=_texto(bruta.get("gpu"), 80),
        idioma=_texto(bruta.get("idioma"), 20),
        zona_horaria=_texto(bruta.get("zona_horaria"), 40),
        red=_texto(bruta.get("red"), 30),
    )


class Registro:
    def __init__(self):
        self.workers: Dict[str, Worker] = {}

    def registrar(self, info: dict, worker_id: Optional[str], ahora: float) -> Worker:
        """Alta nueva o reincorporación (mismo worker_id guardado por el navegador)."""
        w = self.workers.get(worker_id) if worker_id else None
        if w is None:
            w = Worker(id="W" + secrets.token_hex(3).upper(), info=limpiar_info(info), conectado_desde=ahora)
            self.workers[w.id] = w
        else:
            w.info = limpiar_info(info)
        w.estado, w.progreso, w.tarea_actual, w.ultima_comunicacion = "disponible", 0.0, None, ahora
        return w

    def obtener(self, worker_id: str) -> Optional[Worker]:
        return self.workers.get(worker_id)

    def conectados(self) -> List[Worker]:
        return [w for w in self.workers.values() if w.estado != "desconectado"]
