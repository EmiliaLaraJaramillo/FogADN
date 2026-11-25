"""Parámetros del Master. Todo se puede cambiar con variables de entorno FOG_*."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _env(nombre: str, defecto, tipo=str):
    return tipo(os.environ.get(f"FOG_{nombre}", defecto))


PUERTO = _env("PUERTO", 5000, int)
DIR_DATOS = Path(_env("DIR_DATOS", RAIZ / "data"))
DIR_WEB = Path(_env("DIR_WEB", RAIZ / "web"))
BASE_DE_DATOS = Path(_env("BASE_DE_DATOS", RAIZ / "data" / "fog.sqlite"))

TAMANO_BLOQUE = _env("TAMANO_BLOQUE", 16 * 1024 * 1024, int)   # bytes
LATIDO_S = _env("LATIDO_S", 3.0, float)                         # cada cuánto late un worker
TIMEOUT_S = _env("TIMEOUT_S", 10.0, float)                      # sin señal por este tiempo = desconectado
TOKEN_TTL_S = _env("TOKEN_TTL_S", 300.0, float)                 # vigencia del token del QR
REINTENTO_S = _env("REINTENTO_S", 1.0, float)                   # cada cuánto pide trabajo un worker sin tarea
