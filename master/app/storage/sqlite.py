"""Historial de ejecuciones en SQLite (archivo local, sin servidor)."""
import sqlite3
from pathlib import Path
from typing import Dict, List

CAMPOS = ["sesion_id", "archivo", "estado", "inicio", "fin", "duracion_s", "workers_participantes", "tamano_bytes",
          "bloques", "velocidad_media_mb_s", "t_transferencia_s", "t_procesamiento_s", "A", "T", "C", "G", "otros",
          "total_bases"]
TEXTO = {"sesion_id", "archivo", "estado", "inicio", "fin"}
ENTERO = {"workers_participantes", "tamano_bytes", "bloques", "A", "T", "C", "G", "otros", "total_bases"}


def _tipo(c: str) -> str:
    return "TEXT" if c in TEXTO else ("INTEGER" if c in ENTERO else "REAL")


class SqliteStorage:
    def __init__(self, ruta):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        con = self._con()
        try:
            with con:
                cols = ", ".join(f'"{k}" {_tipo(k)}' for k in CAMPOS)
                con.execute(f"CREATE TABLE IF NOT EXISTS ejecuciones (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})")
        finally:
            con.close()

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.ruta)
        con.row_factory = sqlite3.Row
        return con

    def guardar_ejecucion(self, ejecucion: Dict) -> int:
        marcas = ", ".join("?" for _ in CAMPOS)
        nombres = ", ".join(f'"{k}"' for k in CAMPOS)
        con = self._con()
        try:
            with con:
                cur = con.execute(f"INSERT INTO ejecuciones ({nombres}) VALUES ({marcas})", [ejecucion.get(k) for k in CAMPOS])
            return cur.lastrowid
        finally:
            con.close()

    def listar_ejecuciones(self, limite: int = 100) -> List[Dict]:
        con = self._con()
        try:
            filas = con.execute("SELECT * FROM ejecuciones ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
            return [dict(f) for f in filas]
        finally:
            con.close()
