"""Conteo secuencial de un archivo completo en el Master: línea base de comparación y verificación de exactitud."""
import time
from typing import Dict

from .bloques import iterar_bloques, leer_bloque
from .conteo import contar_bloque, sumar

VACIO = {"A": 0, "T": 0, "C": 0, "G": 0, "otros": 0}


def contar_archivo(ruta: str, tamano_bloque: int = 16 * 1024 * 1024) -> Dict:
    """Devuelve conteos, bloques, bytes y tiempos (lectura de disco y conteo por separado)."""
    total, n_bloques, n_bytes = dict(VACIO), 0, 0
    t_lectura = t_conteo = 0.0
    t0 = time.perf_counter()
    for b in iterar_bloques(ruta, tamano_bloque):
        t = time.perf_counter()
        datos = leer_bloque(ruta, b.offset, b.longitud)
        t_lectura += time.perf_counter() - t
        t = time.perf_counter()
        total = sumar(total, contar_bloque(datos))
        t_conteo += time.perf_counter() - t
        n_bloques += 1
        n_bytes += b.longitud
    return dict(conteo=total, bloques=n_bloques, bytes=n_bytes, segundos=time.perf_counter() - t0,
                segundos_lectura=t_lectura, segundos_conteo=t_conteo)
