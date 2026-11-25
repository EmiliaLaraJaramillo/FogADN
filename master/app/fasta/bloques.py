"""Partición de un archivo FASTA en bloques por streaming.

Cada bloque empieza al inicio de una línea y termina justo después de un salto de línea (o en el fin del archivo).
Así ninguna línea de encabezado («>») queda partida entre dos bloques y el conteo de cada bloque es independiente.
El archivo nunca se carga completo: solo se lee la zona alrededor del corte de cada bloque.
"""
import os
from typing import Iterator, NamedTuple

_PASO_BUSQUEDA = 64 * 1024


class Bloque(NamedTuple):
    indice: int
    offset: int
    longitud: int


def _fin_alineado(f, fin_nominal: int, tamano: int) -> int:
    """Primer límite >= fin_nominal que cae justo después de un '\\n' (o el fin del archivo)."""
    if fin_nominal >= tamano:
        return tamano
    f.seek(fin_nominal - 1)
    if f.read(1) == b"\n":
        return fin_nominal
    pos = fin_nominal
    while pos < tamano:
        f.seek(pos)
        trozo = f.read(_PASO_BUSQUEDA)
        if not trozo:
            return tamano
        i = trozo.find(b"\n")
        if i >= 0:
            return pos + i + 1
        pos += len(trozo)
    return tamano


def iterar_bloques(ruta: str, tamano_bloque: int) -> Iterator[Bloque]:
    """Genera los bloques de forma perezosa, uno por uno."""
    if tamano_bloque < 1:
        raise ValueError("El tamaño de bloque debe ser positivo.")
    tamano = os.path.getsize(ruta)
    with open(ruta, "rb") as f:
        offset, indice = 0, 0
        while offset < tamano:
            fin = _fin_alineado(f, offset + tamano_bloque, tamano)
            yield Bloque(indice, offset, fin - offset)
            offset, indice = fin, indice + 1


def leer_bloque(ruta: str, offset: int, longitud: int) -> bytes:
    with open(ruta, "rb") as f:
        f.seek(offset)
        datos = f.read(longitud)
    if len(datos) != longitud:
        raise IOError(f"Lectura incompleta en offset {offset}: {len(datos)} de {longitud} bytes.")
    return datos
