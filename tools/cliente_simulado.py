"""Workers simulados que hablan con el Master por la red real (HTTP + WebSocket), con hilos.

Sirve para probar el protocolo y medir sin celulares:  python tools/cliente_simulado.py --workers 3 --archivo prueba_200mb.fna
Opcional: --caer N hace que el worker 1 se corte tras N bloques (prueba de tolerancia a fallos).
"""
import argparse
import asyncio
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "master"))
from app.fasta.conteo import contar_bloque  # noqa: E402


def http(url, cuerpo=None):
    req = urllib.request.Request(url, data=None if cuerpo is None else json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return r.read()


async def worker(base, token, nombre, caer_tras=None, esperar_sesion=False):
    ws_url = base.replace("http", "ws") + f"/ws/worker?token={token}"
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps(dict(type="hello", worker_id=None, info=dict(modelo=nombre, navegador="simulado", nucleos=4))))
        wid = json.loads(await ws.recv())["worker_id"]
        hechos = 0
        while True:
            await ws.send(json.dumps(dict(type="request_task")))
            m = json.loads(await ws.recv())
            if m["type"] == "no_task":
                if not esperar_sesion and m["motivo"] in ("terminada", "sin_sesion"):
                    return nombre, hechos
                await asyncio.sleep(0.3)
                continue
            if caer_tras is not None and hechos >= caer_tras:
                return nombre, f"{hechos} (caída simulada con un bloque asignado)"
            t0 = time.perf_counter()
            datos = await asyncio.to_thread(http, f"{base}/api/bloques/{m['task_id']}?worker_id={wid}")
            t1 = time.perf_counter()
            c = await asyncio.to_thread(contar_bloque, datos)
            t2 = time.perf_counter()
            await ws.send(json.dumps(dict(type="result", task_id=m["task_id"], conteo=c, bytes=len(datos),
                                          t_transfer_ms=(t1 - t0) * 1e3, t_proceso_ms=(t2 - t1) * 1e3)))
            r = json.loads(await ws.recv())
            assert r["type"] == "ack", r
            hechos += 1


async def main(a):
    base = f"http://127.0.0.1:{a.puerto}"
    token = json.loads(http(f"{base}/api/token"))["url"].split("token=")[1]
    http(f"{base}/api/sesion/iniciar", dict(archivo=a.archivo, tamano_bloque=a.bloque_mb * 1024 * 1024))
    t0 = time.perf_counter()
    tareas = [worker(base, token, f"sim{i + 1}", a.caer if (a.caer is not None and i == 0) else None) for i in range(a.workers)]
    for r in await asyncio.gather(*tareas):
        print("worker", *r)
    s = json.loads(http(f"{base}/api/estado"))["sesion"]
    print(f"{time.perf_counter() - t0:.2f} s  estado={s['estado']}  {s['mb_s']} MB/s  conteo={s['conteo']}")
    esperado = Path(a.dir_datos) / (a.archivo + ".esperado.json")
    if esperado.exists():
        print("exacto:", s["conteo"] == json.loads(esperado.read_text())["esperado"])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--puerto", type=int, default=5000)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--archivo", default="prueba_200mb.fna")
    p.add_argument("--bloque-mb", type=int, default=16)
    p.add_argument("--caer", type=int, default=None)
    p.add_argument("--dir-datos", default=str(Path(__file__).resolve().parents[1] / "data"))
    asyncio.run(main(p.parse_args()))
