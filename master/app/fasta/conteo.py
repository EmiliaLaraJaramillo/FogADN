"""Conteo de bases A, T, C y G en un bloque FASTA.

Reglas (las mismas que aplica el Web Worker del celular):
- Las líneas que empiezan con '>' son encabezados y se ignoran completas.
- A, T, C y G cuentan sin distinguir mayúsculas de minúsculas.
- Cualquier otro carácter que no sea espacio en blanco (N, códigos IUPAC...) se informa como «otros».
- El bloque debe empezar al inicio de una línea (lo garantiza fasta.bloques).

Se cuenta cada letra con bytes.count (corre en C, sin dependencias: sirve también en Termux/Android) sobre todo el bloque
y se restan las de las líneas de encabezado, que son pocas y cortas. La línea base secuencial usa esta misma función,
de modo que la comparación con los celulares no parte de una línea base artificialmente lenta.
"""
from typing import Dict

_BASES = {"A": (b"A", b"a"), "T": (b"T", b"t"), "C": (b"C", b"c"), "G": (b"G", b"g")}
_BLANCOS = (b"\t", b"\n", b"\r", b" ")


def _histograma(datos: bytes) -> Dict[str, int]:
    """Total de bytes, de cada base (mayúscula + minúscula) y de espacios en blanco."""
    h = {b: datos.count(m) + datos.count(mi) for b, (m, mi) in _BASES.items()}
    h["blancos"] = sum(datos.count(c) for c in _BLANCOS)
    h["total"] = len(datos)
    return h


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
        for k, v in _histograma(datos[ini:fin]).items():
            h[k] -= v
    conteo = {b: h[b] for b in _BASES}
    otros = h["total"] - sum(conteo.values()) - h["blancos"]
    return {**conteo, "otros": otros}


def sumar(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]:
    return {k: a.get(k, 0) + b.get(k, 0) for k in ("A", "T", "C", "G", "otros")}


def total_bases(conteo: Dict[str, int]) -> int:
    return sum(conteo[k] for k in "ATCG")
