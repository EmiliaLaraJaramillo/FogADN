"""Evaluación comparativa: secuencial en el Master frente a distribuido con N celulares.

Cada ejecución agrega una fila a data/evaluacion.csv. Después, tools/informe_benchmark.py arma tablas y gráficos.

1) Línea base, en el Master (no necesita celulares ni servidor):
       python tools/benchmark.py secuencial data/GCA_..._genomic.fna --reps 3

2) Distribuido: con el Master en marcha y N celulares ya unidos (QR) y con la pestaña abierta:
       python tools/benchmark.py distribuido GCA_..._genomic.fna --celulares 2 --bloque-mb 8 --reps 2
   (el nombre del archivo es el de la carpeta data/, como en el dashboard)

   --simular lanza N workers simulados en este mismo computador. Sirve solo para comprobar que la herramienta
   funciona; esas filas se marcan «simulado» y el informe no las mezcla con las de celulares.

La exactitud se verifica contra <archivo>.esperado.json (archivos generados) o <archivo>.secuencial.json (el conteo
secuencial de referencia, que se guarda al correr el modo secuencial).
"""
import argparse
import asyncio
import csv
import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "master"))
sys.path.insert(0, str(RAIZ / "tools"))
from app.fasta.secuencial import contar_archivo  # noqa: E402

import os  # noqa: E402
CSV = Path(os.environ.get("FOG_EVAL_DIR", RAIZ / "data")) / "evaluacion.csv"
COLUMNAS = ["fecha", "archivo", "bytes", "modo", "celulares", "bloque_mb", "repeticion", "tiempo_s", "mb_s",
            "t_lectura_o_transf_s", "t_conteo_o_proceso_s", "bloques", "workers_participantes", "exacto", "nota"]


def agregar(fila: dict):
    CSV.parent.mkdir(exist_ok=True)
    nuevo = not CSV.exists()
    with open(CSV, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def referencia(ruta: Path):
    for sufijo, clave in ((".esperado.json", "esperado"), (".secuencial.json", "conteo")):
        f = Path(str(ruta) + sufijo)
        if f.exists():
            return json.loads(f.read_text())[clave]
    return None


def http(url, cuerpo=None):
    req = urllib.request.Request(url, data=None if cuerpo is None else json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def secuencial(a):
    ruta = Path(a.archivo)
    if not ruta.is_absolute():
        ruta = RAIZ / ruta
    for i in range(1, a.reps + 1):
        r = contar_archivo(str(ruta), a.bloque_mb * 1024 * 1024)
        if i == 1 and not Path(str(ruta) + ".secuencial.json").exists():
            Path(str(ruta) + ".secuencial.json").write_text(json.dumps(r, indent=1))
        ref = referencia(ruta)
        exacto = "" if ref is None else str(r["conteo"] == ref)
        mb_s = r["bytes"] / 2**20 / r["segundos"]
        print(f"secuencial #{i}: {r['segundos']:.2f} s  {mb_s:.1f} MB/s  (lectura {r['segundos_lectura']:.2f} s, "
              f"conteo {r['segundos_conteo']:.2f} s)  exacto={exacto}")
        agregar(dict(fecha=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), archivo=ruta.name, bytes=r["bytes"], modo="secuencial",
                     celulares=0, bloque_mb=a.bloque_mb, repeticion=i, tiempo_s=round(r["segundos"], 3), mb_s=round(mb_s, 2),
                     t_lectura_o_transf_s=round(r["segundos_lectura"], 3), t_conteo_o_proceso_s=round(r["segundos_conteo"], 3),
                     bloques=r["bloques"], workers_participantes=0, exacto=exacto, nota=""))


async def distribuido(a):
    base = f"http://127.0.0.1:{a.puerto}"
    ruta = RAIZ / "data" / a.archivo
    ref = referencia(ruta)
    simulados = []
    if a.simular:
        import cliente_simulado as cs
        token = http(f"{base}/api/token")["url"].split("token=")[1]
    for i in range(1, a.reps + 1):
        print(f"\n--- repetición {i}/{a.reps}: {a.celulares} celular(es), bloques de {a.bloque_mb} MB ---")
        if a.simular:
            simulados = [asyncio.create_task(cs.worker(base, token, f"sim{k + 1}", esperar_sesion=True)) for k in range(a.celulares)]
        t_espera, avisado = time.time(), False
        while http(f"{base}/api/estado")["conectados"] < a.celulares:
            if time.time() - t_espera > 180:
                sys.exit(f"Solo hay {http(f'{base}/api/estado')['conectados']} celular(es) conectado(s); se esperaban {a.celulares}.")
            if not avisado:
                print("Esperando celulares conectados…")
                avisado = True
            await asyncio.sleep(1)
        conectados = http(f"{base}/api/estado")["conectados"]
        if conectados != a.celulares and not a.simular:
            print(f"\nAviso: hay {conectados} conectados y se pidieron {a.celulares}; participan todos los conectados.")
        s0 = http(f"{base}/api/sesion/iniciar", dict(archivo=a.archivo, tamano_bloque=a.bloque_mb * 1024 * 1024))
        print(f"\nSesión iniciada: {s0['bloques']} bloques")
        ultimo = -1
        while True:
            s = http(f"{base}/api/estado")["sesion"]
            if int(s["progreso"] // 5) != ultimo:                   # una línea cada 5 % de avance
                ultimo = int(s["progreso"] // 5)
                print(f"{s['progreso']:5.1f} %  {s['mb_s']:6.1f} MB/s  completados {s['completados']}/{s['bloques']}", flush=True)
            if s["estado"] != "en_curso":
                break
            await asyncio.sleep(1)
        for t in simulados:                                          # los simulados esperan sesiones nuevas: se cancelan
            t.cancel()
        await asyncio.gather(*simulados, return_exceptions=True)
        exacto = "" if ref is None else str(s["conteo"] == ref)
        print(f"\n{s['estado']}: {s['transcurrido_s']:.1f} s  {s['mb_s']:.1f} MB/s  workers={s['workers_participantes']}  exacto={exacto}")
        agregar(dict(fecha=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), archivo=a.archivo, bytes=s["bytes"],
                     modo="simulado" if a.simular else "distribuido", celulares=a.celulares, bloque_mb=a.bloque_mb, repeticion=i,
                     tiempo_s=s["transcurrido_s"], mb_s=s["mb_s"], t_lectura_o_transf_s=s["t_transfer_s"],
                     t_conteo_o_proceso_s=s["t_proceso_s"], bloques=s["bloques"],
                     workers_participantes=s["workers_participantes"], exacto=exacto,
                     nota=a.nota + ("" if s["estado"] == "completada" else f" [{s['estado']}]")))
        if a.simular:
            token = http(f"{base}/api/token")["url"].split("token=")[1]
        await asyncio.sleep(2)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("secuencial"); s.add_argument("archivo"); s.add_argument("--reps", type=int, default=3)
    s.add_argument("--bloque-mb", type=int, default=16)
    d = sub.add_parser("distribuido"); d.add_argument("archivo"); d.add_argument("--celulares", type=int, required=True)
    d.add_argument("--bloque-mb", type=int, default=8); d.add_argument("--reps", type=int, default=1)
    d.add_argument("--puerto", type=int, default=5000); d.add_argument("--simular", action="store_true")
    d.add_argument("--nota", default="")
    a = p.parse_args()
    if a.cmd == "secuencial":
        secuencial(a)
    else:
        asyncio.run(distribuido(a))
