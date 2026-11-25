"""Prueba de extremo a extremo con un navegador real (Edge, por Playwright) que hace de celular.

Levanta el Master, abre la página /worker de dos «celulares» (el segundo entra con la sesión ya en marcha), cierra el
primero a mitad de camino y comprueba que el conteo final es exacto. Usa Web Workers reales del navegador.

    python tools/prueba_e2e_navegador.py [archivo.fna en data/] [--bloque-kb 512]
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
PUERTO = 5055
BASE = f"http://127.0.0.1:{PUERTO}"


def get(ruta):
    return json.loads(urllib.request.urlopen(BASE + ruta).read())


def post(ruta, cuerpo):
    req = urllib.request.Request(BASE + ruta, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())


def main(a):
    entorno = dict(os.environ, FOG_PUERTO=str(PUERTO))
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PUERTO), "--log-level", "warning"],
                           cwd=RAIZ / "master", env=entorno)
    try:
        for _ in range(50):
            try:
                get("/api/estado"); break
            except Exception:
                time.sleep(0.2)
        token = get("/api/token")["url"].split("token=")[1]
        post("/api/sesion/iniciar", dict(archivo=a.archivo, tamano_bloque=a.bloque_kb * 1024))
        with sync_playwright() as p:
            nav = p.chromium.launch(channel="msedge", headless=True)
            ctx1 = nav.new_context(viewport=dict(width=390, height=844), is_mobile=True)
            ctx2 = nav.new_context(viewport=dict(width=390, height=844), is_mobile=True)
            p1 = ctx1.new_page()
            p1.on("pageerror", lambda e: print("ERROR JS p1:", e))
            p1.goto(f"{BASE}/worker?token={token}")
            while get("/api/estado")["sesion"]["completados"] < 3:
                time.sleep(0.1)
            ctx1.close()                                          # el celular 1 se «cae» a mitad de la sesión
            print("celular 1 cerrado con", get("/api/estado")["sesion"]["completados"], "bloques completados")
            p2 = ctx2.new_page()                                   # entra el celular 2 con la sesión en marcha
            p2.on("pageerror", lambda e: print("ERROR JS p2:", e))
            p2.goto(f"{BASE}/worker?token={token}")
            t0 = time.time()
            while get("/api/estado")["sesion"]["estado"] != "completada" and time.time() - t0 < 120:
                time.sleep(0.2)
            print("texto del celular 2:", p2.inner_text("#estado"), "|", p2.inner_text("#detalle"))
            print("núcleos/navegador/plataforma:", p2.inner_text("#nuc"), "|", p2.inner_text("#nav"), "|", p2.inner_text("#plat"))
            nav.close()
        est = get("/api/estado")
        esperado = json.loads((RAIZ / "data" / (a.archivo + ".esperado.json")).read_text())["esperado"]
        s = est["sesion"]
        print("estado:", s["estado"], "| bloques:", s["completados"], "/", s["bloques"], "| participantes:", s["workers_participantes"])
        print("eventos:", [e["texto"] for e in est["eventos"]])
        exacto = s["conteo"] == esperado
        print("conteo exacto:", exacto)
        return 0 if exacto and s["estado"] == "completada" else 1
    finally:
        srv.terminate()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("archivo", nargs="?", default="prueba_5mb.fna")
    p.add_argument("--bloque-kb", type=int, default=512)
    sys.exit(main(p.parse_args()))
