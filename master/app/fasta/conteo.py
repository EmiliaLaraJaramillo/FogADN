"""Conteo de bases A, T, C y G en un bloque FASTA.

Reglas (las mismas que aplica el Web Worker del celular):
- Las líneas que empiezan con '>' son encabezados y se ignoran completas.
- A, T, C y G cuentan sin distinguir mayúsculas de minúsculas.
- Cualquier otro carácter que no sea espacio en blanco (N, códigos IUPAC...) se informa como «otros».
- El bloque debe empezar al inicio de una línea (lo garantiza fasta.bloques).

Se hace un histograma de bytes (np.bincount) de todo el bloque y se le restan los de las líneas de encabezado, que son
pocas y cortas. Es la implementación rápida del Master; la línea base secuencial usa esta misma función, de modo que la
comparación con los celulares no parte de una línea base artificialmente lenta.
"""
from typing import Dict

import numpy as np

_BLANCOS = (9, 10, 13, 32)
_BASES = {"A": (65, 97), "T": (84, 116), "C": (67, 99), "G": (71, 103)}


def _histograma(datos) -> np.ndarray:
    return np.bincount(np.frombuffer(datos, dtype=np.uint8), minlength=256)


def _encabezados(datos: bytes):
    """Rangos (inicio, fin) de las líneas que empiezan con '>' (inicio de bloque o tras '\n')."""
    pos = datos.find(b">")
    while pos != -1:
        if pos == 0 or datos[pos - 1] == 10:
            fin = datos.find(b"\n", pos)
            fin = len(datos) if fin == -1 else fin
            yield pos, fin
            pos = datos.find(b">", fin)
        else:
            pos = datos.find(b">", pos + 1)


def contar_bloque(datos: bytes) -> Dict[str, int]:
    h = _histograma(datos)
    for ini, fin in _encabezados(datos):
        h = h - _histograma(datos[ini:fin])
    conteo = {b: int(h[m] + h[mi]) for b, (m, mi) in _BASES.items()}
    otros = int(h.sum()) - sum(conteo.values()) - int(sum(h[b] for b in _BLANCOS))
    return {**conteo, "otros": otros}


def sumar(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]:
    return {k: a.get(k, 0) + b.get(k, 0) for k in ("A", "T", "C", "G", "otros")}


def total_bases(conteo: Dict[str, int]) -> int:
    return sum(conteo[k] for k in "ATCG")
