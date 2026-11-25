"""Conteo secuencial en el Master de un .fna (línea base de la evaluación). Guarda <archivo>.secuencial.json.
    python tools/referencia_secuencial.py data/archivo.fna [--bloque-mb 16]
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "master"))
from app.fasta.secuencial import contar_archivo  # noqa: E402

p = argparse.ArgumentParser(); p.add_argument("archivo"); p.add_argument("--bloque-mb", type=int, default=16)
a = p.parse_args()
r = contar_archivo(a.archivo, a.bloque_mb * 1024 * 1024)
r["mb_s"] = r["bytes"] / 2**20 / r["segundos"]; r["bloque_mb"] = a.bloque_mb
Path(a.archivo + ".secuencial.json").write_text(json.dumps(r, indent=1))
print(json.dumps(r, indent=1))
