"""Genera un .fna de prueba con conteo conocido (queda en <salida>.esperado.json).

Uso:  python tools/generar_fna.py data/prueba_50mb.fna --mb 50 [--ancho 80] [--semilla 42]

Mezcla encabezados, líneas de ancho fijo, algo de minúsculas y de N. Los conteos esperados se calculan sobre lo que se
escribe (no sobre el azar teórico), de modo que sirven para verificar exactitud.
"""
import argparse
import json
import os
import random
import sys
from pathlib import Path


ALFABETO = bytes.maketrans(bytes(range(256)), bytes(b"ACGT"[i % 4] for i in range(256)))


def generar(ruta: str, mb: float, ancho: int, semilla: int) -> dict:
    rng = random.Random(semilla)
    objetivo = int(mb * 1024 * 1024)
    esperado = {"A": 0, "T": 0, "C": 0, "G": 0, "otros": 0}
    escrito = 0
    with open(ruta, "wb") as f:
        n = 0
        while escrito < objetivo:
            n += 1
            enc = f">seq{n} organismo_prueba semilla={semilla}\n".encode()
            largo = min(rng.randint(1_000_000, 8_000_000), max(objetivo - escrito, ancho))
            seq = bytearray(os.urandom(largo).translate(ALFABETO))
            for _ in range(max(1, largo // 5000)):          # tramos en minúscula (soft-masking)
                i = rng.randrange(largo)
                seq[i:i + 200] = bytes(seq[i:i + 200]).lower()
            for _ in range(max(1, largo // 20000)):          # tramos de N
                i = rng.randrange(largo)
                seq[i:i + 50] = b"N" * len(seq[i:i + 50])
            cuerpo = b"\n".join(bytes(seq[i:i + ancho]) for i in range(0, largo, ancho)) + b"\n"
            f.write(enc)
            f.write(cuerpo)
            escrito += len(enc) + len(cuerpo)
            for b in "ATCG":                                  # conteo independiente del código que se prueba
                esperado[b] += cuerpo.count(b.encode()) + cuerpo.count(b.lower().encode())
            esperado["otros"] += cuerpo.count(b"N") + cuerpo.count(b"n")
    info = dict(archivo=Path(ruta).name, bytes=escrito, semilla=semilla, esperado=esperado)
    Path(ruta + ".esperado.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("salida")
    p.add_argument("--mb", type=float, default=50)
    p.add_argument("--ancho", type=int, default=80)
    p.add_argument("--semilla", type=int, default=42)
    a = p.parse_args()
    print(json.dumps(generar(a.salida, a.mb, a.ancho, a.semilla), indent=1))
