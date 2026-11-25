import pytest

import generar_fna
from app import config
from app.coordinador import Coordinador
from app.fasta.conteo import contar_bloque
from app.fasta.bloques import leer_bloque


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def entorno(tmp_path):
    ruta = str(tmp_path / "t.fna")
    info = generar_fna.generar(ruta, mb=1.2, ancho=80, semilla=3)
    reloj = Reloj()
    c = Coordinador(reloj)
    c.iniciar_sesion(ruta, 256 * 1024)           # ~5 bloques
    return c, reloj, ruta, info


def procesar(c, wid, ruta, tarea):
    datos = leer_bloque(ruta, tarea["offset"], tarea["longitud"])
    return c.resultado(wid, tarea["task_id"], contar_bloque(datos), tarea["longitud"], 5, 2)


def pedir(c, wid):
    clase, datos = c.pedir_tarea(wid)
    assert clase == "task", (clase, datos)
    return datos


def test_dos_workers_reparten_y_el_total_es_exacto(entorno):
    c, _, ruta, info = entorno
    a, b = c.hello({}, None).id, c.hello({}, None).id
    n = 0
    while c.estado_sesion == "en_curso":
        for wid in (a, b):
            clase, t = c.pedir_tarea(wid)
            if clase == "task":
                assert procesar(c, wid, ruta, t) == (True, "ok")
                n += 1
    s = c.snapshot()["sesion"]
    assert s["estado"] == "completada" and s["conteo"] == info["esperado"] and s["completados"] == n
    assert c.registro.obtener(a).bloques_procesados > 0 and c.registro.obtener(b).bloques_procesados > 0


def test_desconexion_devuelve_bloques_y_otro_worker_los_toma(entorno):
    c, _, ruta, info = entorno
    a, b = c.hello({}, None).id, c.hello({}, None).id
    t1 = pedir(c, a)
    assert c.snapshot()["sesion"]["asignados"] == 1
    assert c.desconectar(a) == [t1["task_id"]]
    assert c.snapshot()["sesion"]["asignados"] == 0
    t2 = pedir(c, b)
    assert t2["task_id"] == t1["task_id"] and t2["intento"] == 2      # vuelve al frente de la cola
    procesar(c, b, ruta, t2)
    while c.estado_sesion == "en_curso":
        procesar(c, b, ruta, pedir(c, b))
    assert c.snapshot()["sesion"]["conteo"] == info["esperado"]


def test_flujo_completo_con_caida_y_worker_nuevo_a_mitad(entorno):
    c, _, ruta, info = entorno
    a = c.hello({}, None).id
    ta = pedir(c, a)
    procesar(c, a, ruta, ta)                                   # a completa 1 bloque
    tb = pedir(c, a)                                           # a toma otro y se cae sin terminarlo
    c.desconectar(a)
    n = c.hello({"modelo": "Nuevo"}, None).id                  # entra uno nuevo con la sesión en marcha
    while c.estado_sesion == "en_curso":
        procesar(c, n, ruta, pedir(c, n))
    s = c.snapshot()["sesion"]
    assert s["conteo"] == info["esperado"]
    assert s["workers_participantes"] == 2


def test_resultado_duplicado_no_se_suma_dos_veces(entorno):
    c, _, ruta, info = entorno
    a = c.hello({}, None).id
    t = pedir(c, a)
    assert procesar(c, a, ruta, t) == (True, "ok")
    antes = dict(c.cola.conteo)
    assert procesar(c, a, ruta, t) == (False, "duplicado")
    assert c.cola.conteo == antes and c.cola.duplicados_rechazados == 1


def test_resultado_tardio_de_worker_caido_cuenta_una_sola_vez(entorno):
    c, _, ruta, info = entorno
    a, b = c.hello({}, None).id, c.hello({}, None).id
    t = pedir(c, a)
    c.desconectar(a)
    t_b = pedir(c, b)                                           # reasignada a b
    assert t_b["task_id"] == t["task_id"]
    assert procesar(c, a, ruta, t) == (True, "ok")              # llega primero el resultado tardío de a
    assert procesar(c, b, ruta, t_b) == (False, "duplicado")    # el de b es duplicado
    assert c.cola.bytes_completados == t["longitud"]


@pytest.mark.parametrize("conteo,n_bytes,motivo", [
    ({"A": 1}, None, "conteo_mal_formado"),
    ({"A": -1, "T": 0, "C": 0, "G": 0, "otros": 0}, None, "conteo_mal_formado"),
    ({"A": "1", "T": 0, "C": 0, "G": 0, "otros": 0}, None, "conteo_mal_formado"),
    ({"A": 1, "T": 0, "C": 0, "G": 0, "otros": 0}, 1, "bytes_no_coinciden"),
    ({"A": 10**9, "T": 0, "C": 0, "G": 0, "otros": 0}, None, "conteo_excede_bloque"),
])
def test_resultados_invalidos_se_rechazan(entorno, conteo, n_bytes, motivo):
    c, *_ = entorno
    a = c.hello({}, None).id
    t = pedir(c, a)
    ok, m = c.resultado(a, t["task_id"], conteo, t["longitud"] if n_bytes is None else n_bytes)
    assert (ok, m) == (False, motivo)
    assert c.cola.conteo["A"] == 0 and c.registro.obtener(a).errores == 1


def test_timeout_sin_senal_desconecta_y_reasigna(entorno):
    c, reloj, *_ = entorno
    a, b = c.hello({}, None).id, c.hello({}, None).id
    pedir(c, a)
    reloj.t += config.TIMEOUT_S - 1
    c.latido(b)
    assert c.revisar_timeouts() == []
    reloj.t += 2
    assert c.revisar_timeouts() == [a]                          # b latió hace 2 s; a, hace más del límite
    assert c.registro.obtener(a).estado == "desconectado"
    assert c.snapshot()["sesion"]["pendientes"] == len(c.cola.tareas)


def test_reconexion_con_el_mismo_id(entorno):
    c, *_ = entorno
    a = c.hello({"modelo": "X"}, None).id
    c.desconectar(a)
    again = c.hello({"modelo": "X"}, a)
    assert again.id == a and again.estado == "disponible" and len(c.registro.workers) == 1


def test_info_ausente_figura_como_no_disponible():
    c = Coordinador()
    w = c.hello({"navegador": "Safari", "nucleos": 0, "memoria_gb": None}, None)
    assert w.info["modelo"] == "No disponible" and w.info["nucleos"] == "No disponible"
    assert w.info["memoria_gb"] == "No disponible" and w.info["navegador"] == "Safari"


def test_no_se_inicia_una_segunda_sesion_en_curso(entorno):
    c, _, ruta, _ = entorno
    with pytest.raises(ValueError):
        c.iniciar_sesion(ruta)


def test_historial_se_guarda_una_vez_al_completar_y_al_cancelar(tmp_path):
    from app.storage.sqlite import SqliteStorage
    ruta = str(tmp_path / "h.fna")
    info = generar_fna.generar(ruta, mb=1, ancho=80, semilla=9)
    c = Coordinador(Reloj(), storage=SqliteStorage(tmp_path / "h.sqlite"))
    c.iniciar_sesion(ruta, 256 * 1024)
    a = c.hello({}, None).id
    while c.estado_sesion == "en_curso":
        procesar(c, a, ruta, pedir(c, a))
    c._guardar()                                                    # una segunda llamada no duplica
    filas = c.storage.listar_ejecuciones()
    assert len(filas) == 1 and filas[0]["estado"] == "completada" and filas[0]["A"] == info["esperado"]["A"]
    assert filas[0]["workers_participantes"] == 1 and filas[0]["archivo"] == "h.fna"
    c.iniciar_sesion(ruta, 256 * 1024)
    c.cancelar_sesion()
    filas = c.storage.listar_ejecuciones()
    assert [f["estado"] for f in filas] == ["cancelada", "completada"]      # la más reciente primero
