import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import generar_fna
from app import config
from app.coordinador import Coordinador
from app.fasta.conteo import contar_bloque
from app.transport.api import crear_app

INFO = {"modelo": "Simulado", "navegador": "pytest", "nucleos": 4}


@pytest.fixture
def sistema(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DIR_DATOS", tmp_path)
    info = generar_fna.generar(str(tmp_path / "t.fna"), mb=1.5, ancho=80, semilla=5)
    app = crear_app(Coordinador(), vigilar=False)
    with TestClient(app) as cliente:
        yield cliente, app.state.coord, info


def token(cliente):
    return cliente.get("/api/token").json()["url"].split("token=")[1]


def conectar(cliente, tk, worker_id=None):
    ws = cliente.websocket_connect(f"/ws/worker?token={tk}" + (f"&worker_id={worker_id}" if worker_id else ""))
    ws.__enter__()
    ws.send_json(dict(type="hello", info=INFO, worker_id=worker_id))
    return ws, ws.receive_json()


def un_bloque(cliente, ws, wid, ok=True):
    ws.send_json(dict(type="request_task"))
    t = ws.receive_json()
    if t["type"] != "task":
        return t
    r = cliente.get(f"/api/bloques/{t['task_id']}", params=dict(worker_id=wid))
    assert r.status_code == 200 and len(r.content) == t["longitud"]
    if ok:
        ws.send_json(dict(type="result", task_id=t["task_id"], conteo=contar_bloque(r.content), bytes=len(r.content),
                          t_transfer_ms=3, t_proceso_ms=1))
        return t, ws.receive_json()
    return t, None


def test_api_archivos_token_y_qr(sistema):
    c, _, _ = sistema
    assert [a["nombre"] for a in c.get("/api/archivos").json()] == ["t.fna"]
    r = c.get("/api/token").json()
    assert "/worker?token=" in r["url"] and r["qr_svg"].startswith("<svg") and r["ips"] is not None


def test_token_invalido_se_rechaza(sistema):
    c, *_ = sistema
    with pytest.raises(WebSocketDisconnect) as e:
        with c.websocket_connect("/ws/worker?token=falso"):
            pass
    assert e.value.code == 4401


def test_iniciar_valida_extension_y_existencia(sistema):
    c, *_ = sistema
    assert c.post("/api/sesion/iniciar", json={"archivo": "x.txt"}).status_code == 400
    assert c.post("/api/sesion/iniciar", json={"archivo": "no_existe.fna"}).status_code == 404
    assert c.post("/api/sesion/iniciar", json={"archivo": "../../etc/t.fna"}).status_code in (200, 404)


def test_extremo_a_extremo_con_dos_workers_y_un_tercero_a_mitad(sistema):
    c, coord, info = sistema
    c.post("/api/sesion/iniciar", json={"archivo": "t.fna", "tamano_bloque": 128 * 1024})
    tk = token(c)
    (w1, h1), (w2, h2) = conectar(c, tk), conectar(c, tk)
    assert h1["type"] == "welcome" and h1["worker_id"] != h2["worker_id"]
    ids = [h1["worker_id"], h2["worker_id"]]
    # el worker 1 toma un bloque y se cae sin entregarlo
    t_perdido, _ = un_bloque(c, w1, ids[0], ok=False)
    w1.__exit__(None, None, None)
    assert coord.snapshot()["sesion"]["asignados"] == 0
    w3, h3 = conectar(c, tk)                                      # entra uno nuevo con la sesión en marcha
    activos = [(w2, ids[1]), (w3, h3["worker_id"])]
    for _ in range(400):
        for ws, wid in activos:
            r = un_bloque(c, ws, wid)
        if coord.estado_sesion != "en_curso":
            break
    s = c.get("/api/estado").json()
    assert s["sesion"]["estado"] == "completada" and s["sesion"]["conteo"] == info["esperado"]
    assert s["sesion"]["workers_participantes"] == 2 and s["sesion"]["progreso"] == 100.0
    assert coord.cola.tareas[t_perdido["task_id"]].intentos == 2
    ws_ids = {w["id"]: w for w in s["workers"]}
    assert ws_ids[ids[0]]["estado"] == "desconectado"
    for ws, _ in activos:
        ws.__exit__(None, None, None)


def test_bloque_solo_para_el_worker_asignado(sistema):
    c, *_ = sistema
    c.post("/api/sesion/iniciar", json={"archivo": "t.fna", "tamano_bloque": 256 * 1024})
    tk = token(c)
    (w1, h1), (w2, h2) = conectar(c, tk), conectar(c, tk)
    w1.send_json(dict(type="request_task"))
    t = w1.receive_json()
    assert c.get(f"/api/bloques/{t['task_id']}", params=dict(worker_id=h2["worker_id"])).status_code == 409
    assert c.get("/api/bloques/inexistente", params=dict(worker_id=h1["worker_id"])).status_code == 404
    w1.__exit__(None, None, None); w2.__exit__(None, None, None)


def test_resultado_duplicado_recibe_reject(sistema):
    c, coord, _ = sistema
    c.post("/api/sesion/iniciar", json={"archivo": "t.fna", "tamano_bloque": 256 * 1024})
    ws, h = conectar(c, token(c))
    t, ack = un_bloque(c, ws, h["worker_id"])
    assert ack["type"] == "ack"
    ws.send_json(dict(type="result", task_id=t["task_id"], conteo=dict(A=1, T=0, C=0, G=0, otros=0), bytes=t["longitud"]))
    r = ws.receive_json()
    assert r["type"] == "reject" and r["motivo"] == "duplicado"
    ws.__exit__(None, None, None)


def test_mensajes_sin_hello_y_desconocidos(sistema):
    c, *_ = sistema
    with c.websocket_connect(f"/ws/worker?token={token(c)}") as ws:
        ws.send_json(dict(type="request_task"))
        assert ws.receive_json()["motivo"] == "falta_hello"
        ws.send_json(dict(type="hello", info={}))
        ws.receive_json()
        ws.send_json(dict(type="algo"))
        assert ws.receive_json()["motivo"] == "mensaje_desconocido"


def test_dashboard_recibe_el_estado(sistema):
    c, *_ = sistema
    with c.websocket_connect("/ws/dashboard") as d:
        assert d.receive_json()["type"] == "state"
        ws, _ = conectar(c, token(c))
        assert d.receive_json()["conectados"] == 1
        ws.__exit__(None, None, None)


def test_worker_registrado_puede_reconectarse_con_token_vencido(sistema):
    c, coord, _ = sistema
    ws, h = conectar(c, token(c))
    ws.__exit__(None, None, None)
    coord.tokens._vence.clear()                                   # el token del QR venció
    with pytest.raises(WebSocketDisconnect) as e:                 # un celular nuevo ya no puede entrar con él
        with c.websocket_connect("/ws/worker?token=viejo"):
            pass
    assert e.value.code == 4401
    ws2, h2 = conectar(c, "viejo", worker_id=h["worker_id"])      # pero el ya registrado sí vuelve
    assert h2["type"] == "welcome" and h2["worker_id"] == h["worker_id"]
    ws2.__exit__(None, None, None)


def test_subida_por_streaming_y_validaciones(sistema):
    c, *_ = sistema
    r = c.post("/api/archivos/subir?nombre=nuevo.fna", content=b">x\nACGT\n" * 1000)
    assert r.status_code == 200 and r.json()["bytes"] == 8000
    assert "nuevo.fna" in [a["nombre"] for a in c.get("/api/archivos").json()]
    assert c.post("/api/archivos/subir?nombre=nuevo.fna", content=b"x").status_code == 409
    assert c.post("/api/archivos/subir?nombre=malo.txt", content=b"x").status_code == 400
    assert c.post("/api/archivos/subir?nombre=vacio.fna", content=b"").status_code == 400
    assert not list(config.DIR_DATOS.glob("*.parte"))             # no quedan archivos parciales


def test_exportar_resultados_csv_y_json(sistema):
    c, coord, info = sistema
    assert c.get("/api/resultado.csv").status_code == 404
    coord.iniciar_sesion(str(config.DIR_DATOS / "t.fna"), 512 * 1024)
    ws, h = conectar(c, token(c))
    while coord.estado_sesion == "en_curso":
        un_bloque(c, ws, h["worker_id"])
    j = c.get("/api/resultado.json").json()
    assert j["A"] == info["esperado"]["A"] and j["total_bases"] == sum(info["esperado"][k] for k in "ATCG")
    assert j["estado"] == "completada" and j["workers_participantes"] == 1
    filas = c.get("/api/resultado.csv").text.splitlines()
    assert filas[0].lstrip("﻿") == "campo,valor" and any(f.startswith("G,") for f in filas)
    ws.__exit__(None, None, None)


def test_historial_api_y_exportacion(tmp_path, monkeypatch):
    from app.storage.sqlite import SqliteStorage
    monkeypatch.setattr(config, "DIR_DATOS", tmp_path)
    generar_fna.generar(str(tmp_path / "t.fna"), mb=1, ancho=80, semilla=2)
    app = crear_app(Coordinador(storage=SqliteStorage(tmp_path / "h.sqlite")), vigilar=False)
    with TestClient(app) as c:
        assert c.get("/api/historial").json() == []
        c.post("/api/sesion/iniciar", json={"archivo": "t.fna", "tamano_bloque": 512 * 1024})
        ws, h = conectar(c, token(c))
        while app.state.coord.estado_sesion == "en_curso":
            un_bloque(c, ws, h["worker_id"])
        lista = c.get("/api/historial").json()
        assert len(lista) == 1 and lista[0]["estado"] == "completada" and lista[0]["total_bases"] > 0
        assert len(c.get("/api/historial.json").json()) == 1
        csv_ = c.get("/api/historial.csv").text.lstrip("﻿").splitlines()
        assert csv_[0].startswith("id,sesion_id,archivo") and len(csv_) == 2
        ws.__exit__(None, None, None)
