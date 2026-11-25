"""Transporte: rutas HTTP y WebSockets de FastAPI. No contiene reglas de reparto (están en coordinador.py)."""
import asyncio
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

import segno
import csv
import io
import json

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import config
from ..coordinador import Coordinador
from ..fasta.bloques import leer_bloque


def ips_locales() -> List[str]:
    """IPs IPv4 del Master; la primera es la de la ruta por defecto (la de la red Wi-Fi, normalmente)."""
    ips: List[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))               # no envía nada: solo consulta la ruta
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return ips


def crear_app(coord: Optional[Coordinador] = None, vigilar: bool = True) -> FastAPI:
    coord = coord or Coordinador()

    @asynccontextmanager
    async def ciclo(app: FastAPI):
        tarea = asyncio.create_task(vigilante()) if vigilar else None
        yield
        if tarea:
            tarea.cancel()

    app = FastAPI(title="Fog Computing ADN · Master", lifespan=ciclo)
    app.state.coord = coord
    tableros: set = set()

    def con_master(estado: dict) -> dict:
        ips = ips_locales()
        estado["master"] = dict(nombre=socket.gethostname(), ip=ips[0] if ips else "127.0.0.1", ips=ips, puerto=config.PUERTO)
        return estado

    async def difundir():
        if not tableros:
            return
        estado = con_master(coord.snapshot())
        for ws in list(tableros):
            try:
                await ws.send_json(dict(type="state", **estado))
            except Exception:
                tableros.discard(ws)

    async def vigilante():
        while True:
            await asyncio.sleep(1.0)
            coord.revisar_timeouts()
            await difundir()

    # --- control (dashboard) ----------------------------------------------------------------------------------
    @app.get("/api/archivos")
    def archivos():
        carpeta = config.DIR_DATOS
        lista = sorted(p for p in carpeta.glob("*.fna") if p.is_file()) if carpeta.is_dir() else []
        return [dict(nombre=p.name, bytes=p.stat().st_size) for p in lista]

    @app.post("/api/sesion/iniciar")
    async def iniciar(cuerpo: dict):
        nombre = Path(str(cuerpo.get("archivo", ""))).name        # solo archivos de la carpeta de datos
        if not nombre.lower().endswith(".fna"):
            raise HTTPException(400, "El archivo debe tener extensión .fna")
        ruta = config.DIR_DATOS / nombre
        try:
            r = await run_in_threadpool(coord.iniciar_sesion, str(ruta), cuerpo.get("tamano_bloque"))
        except FileNotFoundError:
            raise HTTPException(404, "Archivo no encontrado en la carpeta de datos")
        except ValueError as e:
            raise HTTPException(409, str(e))
        await difundir()
        return r

    @app.post("/api/sesion/cancelar")
    async def cancelar():
        coord.cancelar_sesion()
        await difundir()
        return coord.snapshot()["sesion"]

    @app.get("/api/estado")
    def estado():
        return con_master(coord.snapshot())

    @app.post("/api/archivos/subir")
    async def subir(request: Request, nombre: str = Query(...)):
        """Recibe el archivo por streaming (nunca completo en memoria) y lo guarda en la carpeta de datos."""
        limpio = Path(nombre).name
        if not limpio.lower().endswith(".fna") or limpio.startswith("."):
            raise HTTPException(400, "El archivo debe tener extensión .fna")
        config.DIR_DATOS.mkdir(parents=True, exist_ok=True)
        destino, parcial = config.DIR_DATOS / limpio, config.DIR_DATOS / (limpio + ".parte")
        if destino.exists():
            raise HTTPException(409, "Ya existe un archivo con ese nombre")
        n = 0
        try:
            with open(parcial, "wb") as f:
                async for trozo in request.stream():
                    f.write(trozo)
                    n += len(trozo)
            if n == 0:
                raise HTTPException(400, "Archivo vacío")
            parcial.replace(destino)
        finally:
            if parcial.exists():
                parcial.unlink()
        return dict(nombre=limpio, bytes=n)

    @app.get("/api/historial")
    def historial():
        return coord.storage.listar_ejecuciones() if coord.storage else []

    @app.get("/api/historial.json")
    def historial_json():
        return Response(json.dumps(historial(), indent=1, ensure_ascii=False), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="historial.json"'})

    @app.get("/api/historial.csv")
    def historial_csv():
        filas = historial()
        salida = io.StringIO()
        if filas:
            w = csv.DictWriter(salida, fieldnames=list(filas[0]))
            w.writeheader()
            w.writerows(filas)
        return Response("﻿" + salida.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="historial.csv"'})

    @app.get("/api/resultado.json")
    def resultado_json():
        r = coord.resultado_final()
        if r is None:
            raise HTTPException(404, "Todavía no hay resultados")
        return Response(json.dumps(r, indent=1, ensure_ascii=False), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="resultado_{r["archivo"]}.json"'})

    @app.get("/api/resultado.csv")
    def resultado_csv():
        r = coord.resultado_final()
        if r is None:
            raise HTTPException(404, "Todavía no hay resultados")
        salida = io.StringIO()
        w = csv.writer(salida)
        w.writerow(["campo", "valor"])
        w.writerows(r.items())
        return Response("﻿" + salida.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="resultado_{r["archivo"]}.csv"'})

    @app.get("/api/token")
    def token(ip: Optional[str] = None):
        """Token nuevo y QR hacia la página del celular. `ip` permite elegir otra interfaz de red del Master."""
        ips = ips_locales()
        host = ip or (ips[0] if ips else "127.0.0.1")
        url = f"http://{host}:{config.PUERTO}/worker?token={coord.tokens.crear()}"
        return dict(url=url, ip=host, ips=ips, vigencia_s=config.TOKEN_TTL_S,
                    qr_svg=segno.make(url, error="m").svg_inline(scale=1, border=4, dark="#000000", light="#ffffff", omitsize=True))

    # --- datos para los celulares -----------------------------------------------------------------------------
    @app.get("/api/bloques/{task_id}")
    async def bloque(task_id: str, worker_id: str = Query(...)):
        t = coord.cola.tareas.get(task_id) if coord.cola else None
        if t is None:
            raise HTTPException(404, "Tarea desconocida")
        if t.estado != "asignada" or t.worker_id != worker_id:
            raise HTTPException(409, "La tarea no está asignada a este worker")
        datos = await run_in_threadpool(leer_bloque, coord.cola.ruta, t.offset, t.longitud)
        return Response(content=datos, media_type="application/octet-stream")

    # --- WebSockets -------------------------------------------------------------------------------------------
    @app.websocket("/ws/dashboard")
    async def ws_dashboard(ws: WebSocket):
        await ws.accept()
        tableros.add(ws)
        try:
            await ws.send_json(dict(type="state", **con_master(coord.snapshot())))
            while True:
                await ws.receive_text()                         # el dashboard no envía nada; mantiene la conexión
        except WebSocketDisconnect:
            pass
        finally:
            tableros.discard(ws)

    @app.websocket("/ws/worker")
    async def ws_worker(ws: WebSocket, token: str = Query(""), worker_id: str = Query("")):
        # El token autoriza el ingreso inicial; un worker ya registrado puede reconectarse aunque el token haya vencido.
        if not (coord.tokens.valido(token) or coord.registro.obtener(worker_id)):
            await ws.close(code=4401)                          # token inválido o vencido
            return
        await ws.accept()
        worker_id: Optional[str] = None
        try:
            while True:
                m = await ws.receive_json()
                tipo = m.get("type")
                if tipo == "hello":
                    w = coord.hello(m.get("info", {}), m.get("worker_id"))
                    worker_id = w.id
                    await ws.send_json(dict(type="welcome", worker_id=w.id, latido_s=config.LATIDO_S,
                                            reintento_s=config.REINTENTO_S))
                elif worker_id is None:
                    await ws.send_json(dict(type="error", motivo="falta_hello"))
                elif tipo == "heartbeat":
                    coord.latido(worker_id, m.get("progreso"))
                elif tipo == "request_task":
                    clase, datos = coord.pedir_tarea(worker_id)
                    await ws.send_json(dict(type=clase, **datos))
                elif tipo == "result":
                    ok, motivo = coord.resultado(worker_id, str(m.get("task_id")), m.get("conteo"), m.get("bytes"),
                                                 m.get("t_transfer_ms", 0), m.get("t_proceso_ms", 0))
                    await ws.send_json(dict(type="ack" if ok else "reject", task_id=m.get("task_id"), motivo=motivo))
                else:
                    await ws.send_json(dict(type="error", motivo="mensaje_desconocido"))
                await difundir()
        except WebSocketDisconnect:
            pass
        finally:
            if worker_id:
                coord.desconectar(worker_id, "conexión cerrada")
                await difundir()

    # --- páginas ----------------------------------------------------------------------------------------------
    @app.get("/worker")
    def pagina_worker():
        f = config.DIR_WEB / "worker" / "worker.html"
        if f.is_file():
            return FileResponse(f)
        return JSONResponse({"detalle": "La página del celular se construye en la Fase 3."}, status_code=501)

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return Response(status_code=204)

    @app.get("/")
    def pagina_dashboard():
        f = config.DIR_WEB / "dashboard" / "index.html"
        if f.is_file():
            return FileResponse(f)
        return JSONResponse({"detalle": "El dashboard se construye en la Fase 5.", "estado": "/api/estado"})

    if config.DIR_WEB.is_dir():
        app.mount("/static", StaticFiles(directory=config.DIR_WEB), name="static")
    return app
