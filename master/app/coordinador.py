"""Lógica del Master, sin red: sesión, workers, tokens y reglas de asignación.

La capa de transporte (FastAPI) solo traduce mensajes a llamadas de esta clase. Así se prueba sin sockets y se puede
sustituir el transporte o el almacenamiento (Cloud) sin tocar el reparto.
"""
import secrets
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from . import config
from .scheduler.cola import Cola
from .workers.registro import Registro, Worker
from .workers.tokens import Tokens


_LETRA = {"pendiente": "p", "asignada": "a", "completada": "c"}


class Coordinador:
    def __init__(self, reloj: Callable[[], float] = time.time, storage=None):
        self.reloj = reloj
        self.storage = storage                 # historial (interfaz Storage); None = sin persistencia
        self._guardada = False
        self.tokens = Tokens(config.TOKEN_TTL_S, reloj)
        self.registro = Registro()
        self.cola: Optional[Cola] = None
        self.archivo: Optional[str] = None
        self.sesion_id: Optional[str] = None
        self.estado_sesion = "sin_sesion"      # sin_sesion | en_curso | completada | cancelada
        self.t_inicio = self.t_fin = 0.0
        self.eventos: List[Dict] = []          # bitácora corta que se muestra en el dashboard

    # --- sesión -----------------------------------------------------------------------------------------------
    def iniciar_sesion(self, ruta: str, tamano_bloque: Optional[int] = None) -> Dict:
        if self.estado_sesion == "en_curso":
            raise ValueError("Ya hay una sesión en curso.")
        if not Path(ruta).is_file():
            raise FileNotFoundError(ruta)
        self.sesion_id = secrets.token_hex(3)
        self.cola = Cola(self.sesion_id, ruta, tamano_bloque or config.TAMANO_BLOQUE)
        self.archivo = ruta
        self.estado_sesion, self.t_inicio, self.t_fin = "en_curso", self.reloj(), 0.0
        self._guardada = False
        for w in self.registro.conectados():
            w.estado, w.progreso, w.bloques_procesados, w.bytes_procesados = "disponible", 0.0, 0, 0
            w.t_proceso_ms = w.t_transfer_ms = 0.0
        self._evento(f"Sesión {self.sesion_id}: {Path(ruta).name}, {len(self.cola.tareas)} bloques")
        return self.snapshot()["sesion"]

    def cancelar_sesion(self):
        if self.estado_sesion != "en_curso":
            return
        self.estado_sesion, self.t_fin = "cancelada", self.reloj()
        for w in self.registro.conectados():
            w.estado, w.tarea_actual, w.progreso = "disponible", None, 0.0
        self._evento("Sesión cancelada")
        self._guardar()

    # --- workers ----------------------------------------------------------------------------------------------
    def hello(self, info: dict, worker_id: Optional[str]) -> Worker:
        w = self.registro.registrar(info, worker_id, self.reloj())
        self._evento(f"{w.id} conectado ({w.info['modelo']}, {w.info['navegador']})")
        return w

    def latido(self, worker_id: str, progreso: Optional[float] = None):
        w = self.registro.obtener(worker_id)
        if w is None or w.estado == "desconectado":
            return
        w.ultima_comunicacion = self.reloj()
        if isinstance(progreso, (int, float)) and w.estado == "procesando":
            w.progreso = max(0.0, min(100.0, float(progreso)))

    def pedir_tarea(self, worker_id: str) -> Tuple[str, Dict]:
        w = self.registro.obtener(worker_id)
        if w is None or w.estado == "desconectado":
            return "error", {"motivo": "worker_no_registrado"}
        w.ultima_comunicacion = self.reloj()
        if self.estado_sesion != "en_curso" or self.cola is None:
            return "no_task", {"motivo": "sin_sesion" if self.estado_sesion != "completada" else "terminada"}
        t = self.cola.asignar(worker_id, self.reloj())
        if t is None:
            return "no_task", {"motivo": "esperando"}     # hay bloques asignados a otros; pueden volver a la cola
        w.estado, w.tarea_actual, w.progreso = "procesando", t.id, 0.0
        return "task", dict(task_id=t.id, indice=t.indice, offset=t.offset, longitud=t.longitud,
                            total=len(self.cola.tareas), intento=t.intentos)

    def resultado(self, worker_id: str, task_id: str, conteo: dict, n_bytes: int,
                  t_transfer_ms: float = 0.0, t_proceso_ms: float = 0.0) -> Tuple[bool, str]:
        w = self.registro.obtener(worker_id)
        if w is None or self.cola is None:
            return False, "sin_sesion"
        w.ultima_comunicacion = self.reloj()
        ok, motivo = self.cola.completar(task_id, worker_id, conteo, n_bytes)
        if w.tarea_actual == task_id:
            w.tarea_actual, w.progreso = None, 0.0
            w.estado = "disponible"
        if not ok:
            if motivo != "duplicado":
                w.errores += 1
            return False, motivo
        w.bloques_procesados += 1
        w.bytes_procesados += n_bytes
        w.t_proceso_ms += max(0.0, float(t_proceso_ms or 0))
        w.t_transfer_ms += max(0.0, float(t_transfer_ms or 0))
        if self.cola.terminada and self.estado_sesion == "en_curso":
            self.estado_sesion, self.t_fin = "completada", self.reloj()
            for x in self.registro.conectados():
                x.estado = "completado"
            self._evento("Sesión completada")
            self._guardar()
        return True, "ok"

    def desconectar(self, worker_id: str, motivo: str = "desconexión") -> List[str]:
        """Marca al worker desconectado y devuelve sus bloques a la cola."""
        w = self.registro.obtener(worker_id)
        if w is None or w.estado == "desconectado":
            return []
        w.estado, w.tarea_actual, w.progreso = "desconectado", None, 0.0
        liberadas = self.cola.liberar_de(worker_id) if self.cola and self.estado_sesion == "en_curso" else []
        self._evento(f"{w.id} desconectado ({motivo})" + (f"; {len(liberadas)} bloque(s) vuelven a la cola" if liberadas else ""))
        return liberadas

    def revisar_timeouts(self) -> List[str]:
        """Desconecta a los workers sin señal por más de TIMEOUT_S. Devuelve sus identificadores."""
        ahora, caidos = self.reloj(), []
        for w in self.registro.conectados():
            if ahora - w.ultima_comunicacion > config.TIMEOUT_S:
                self.desconectar(w.id, "sin señal")
                caidos.append(w.id)
        return caidos

    # --- estado visible ---------------------------------------------------------------------------------------
    def snapshot(self) -> Dict:
        ahora = self.reloj()
        sesion: Dict = dict(estado=self.estado_sesion, id=self.sesion_id)
        if self.cola:
            r = self.cola.resumen()
            fin = self.t_fin or ahora
            dur = max(fin - self.t_inicio, 1e-9)
            total = self.cola.bytes_totales
            sesion.update(archivo=Path(self.archivo).name, bytes=total, bloques=len(self.cola.tareas),
                          pendientes=r["pendiente"], asignados=r["asignada"], completados=r["completada"],
                          progreso=round(100 * self.cola.bytes_completados / total, 2) if total else 100.0,
                          conteo=self.cola.conteo, t_inicio=self.t_inicio, t_fin=self.t_fin,
                          transcurrido_s=round(dur, 2), mb_s=round(self.cola.bytes_completados / 2**20 / dur, 2),
                          duplicados_rechazados=self.cola.duplicados_rechazados, tamano_bloque=self.cola.tamano_bloque,
                          mapa="".join(_LETRA[t.estado] for t in self.cola.tareas.values()),
                          t_transfer_s=round(sum(w.t_transfer_ms for w in self.registro.workers.values()) / 1000, 2),
                          t_proceso_s=round(sum(w.t_proceso_ms for w in self.registro.workers.values()) / 1000, 2),
                          workers_participantes=len({t.completada_por for t in self.cola.tareas.values() if t.completada_por}))
        return dict(ahora=ahora, sesion=sesion, workers=[w.visible() for w in self.registro.workers.values()],
                    conectados=len(self.registro.conectados()), eventos=self.eventos[-12:])

    def _guardar(self):
        """Registra la ejecución en el historial, una sola vez por sesión."""
        if self.storage is None or self._guardada:
            return
        self._guardada = True
        r = self.resultado_final()
        if r is not None:
            self.storage.guardar_ejecucion(dict(r, sesion_id=self.sesion_id))

    def resultado_final(self) -> Optional[Dict]:
        """Resumen exportable de la última sesión (None si no hubo ninguna)."""
        s = self.snapshot()["sesion"]
        if self.cola is None:
            return None
        c = s["conteo"]
        dur = s["transcurrido_s"]
        return {"archivo": s["archivo"], "estado": s["estado"], "tamano_bytes": s["bytes"], "bloques": s["bloques"],
                "tamano_bloque_bytes": s["tamano_bloque"], "workers_participantes": s["workers_participantes"],
                "inicio": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s["t_inicio"])),
                "fin": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s["t_fin"])) if s["t_fin"] else "",
                "duracion_s": dur, "velocidad_media_mb_s": s["mb_s"], "t_transferencia_s": s["t_transfer_s"],
                "t_procesamiento_s": s["t_proceso_s"], "A": c["A"], "T": c["T"], "C": c["C"], "G": c["G"],
                "otros": c["otros"], "total_bases": c["A"] + c["T"] + c["C"] + c["G"]}

    def _evento(self, texto: str):
        self.eventos.append(dict(t=self.reloj(), texto=texto))
